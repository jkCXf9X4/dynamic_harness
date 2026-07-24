from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .task import (
    ActivityEvent,
    ActivityEventType,
    BudgetRequest,
    Escalation,
    Failure,
    ReportPayload,
    Task,
    TaskStatus,
)

if TYPE_CHECKING:
    from ..llm.provider import LLMProvider
    from .runtime import Runtime


AGENT_SYSTEM_PROMPT = (Path(__file__).parent / "agent_system_prompt.txt").read_text()

MAX_TOOL_RESULT_CHARS = 100_000


class Agent:
    def __init__(
        self,
        agent_id: str,
        task: Task,
        runtime: Runtime,
        parent: Agent | None = None,
        *,
        system_prompt: str | None = None,
        safety_max_iterations: int = 500,
        repeated_call_limit: int = 5,
        safety_timeout_seconds: float | None = None,
    ) -> None:
        self.id = agent_id
        self.task = task
        self.parent = parent
        self.children: list[Agent] = []
        self._system_prompt = system_prompt or task.system_prompt
        self._safety_max_iterations = safety_max_iterations
        self.repeated_call_limit = repeated_call_limit
        self._safety_timeout_seconds = safety_timeout_seconds
        self._started_at: float | None = None
        self._messages: list[dict[str, Any]] = []
        self._has_run: bool = False
        self._iteration: int = 0
        self._recent_batches: deque[list[tuple[str, frozenset[tuple[str, object]]]]] | None = None
        self._last_report: ReportPayload | None = None
        self._last_failure: Failure | None = None
        self._pending_child_task: asyncio.Task[None] | None = None
        self._deferred_delegates: list[tuple[str, Agent, asyncio.Task[None]]] | None = None

        self._runtime = runtime
        self._event_bus = runtime.event_bus
        self._tool_registry = runtime.tool_registry
        self._usage_tracker = runtime.usage_tracker
        self._llm = runtime._llm
        self._trace_store = runtime.trace_store
        self._artifact_store = runtime.artifact_store
        self._generated_root = runtime.generated_root

    @property
    def llm(self) -> LLMProvider | None:
        return self._llm

    @property
    def guidelines(self) -> str:
        return AGENT_SYSTEM_PROMPT

    async def run(self) -> None:
        llm = self.llm
        if not llm:
            self.fail("No LLM provider configured")
            return

        user_message = self.task.description
        if self.task.role:
            user_message = f"[ROLE] {self.task.role}\n\n[TASK] {self.task.description}"
        self._messages = [
            {"role": "system", "content": self._system_prompt or AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]
        self._has_run = True
        self._iteration = 0
        self._recent_batches = deque(maxlen=self.repeated_call_limit)
        self._started_at = time.monotonic()
        try:
            await self._run_loop()
        except asyncio.CancelledError:
            if self._pending_child_task and not self._pending_child_task.done():
                self._pending_child_task.cancel()
                try:
                    await self._pending_child_task
                except asyncio.CancelledError:
                    pass
            if not self._last_report and not self._last_failure:
                self.fail("Agent cancelled")
            raise

    async def continue_with_input(self, user_message: str) -> None:
        if not self._has_run:
            self.task.description = user_message
            await self.run()
            return
        self.task.status = TaskStatus.running
        self._messages.append({"role": "user", "content": user_message})
        await self._run_loop()

    async def _llm_call_with_retry(self, tools: list[dict], max_retries: int = 3) -> Any:
        llm = self.llm
        assert llm is not None

        base_delay = 1.0
        last_error: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                return await llm.generate_with_tools(self._messages, tools)
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                is_retryable = any(
                    keyword in error_str
                    for keyword in (
                        "rate_limit", "rate limit", "429", "too many requests",
                        "server_error", "500", "502", "503", "504",
                        "timeout", "temporary", "connection", "network",
                        "overloaded", "capacity",
                    )
                )
                if not is_retryable or attempt >= max_retries:
                    raise
                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)

        raise last_error  # type: ignore[misc]

    async def _run_loop(self) -> None:
        tools = self._tool_registry.openai_schemas()

        while True:
            self._iteration += 1
            if (
                self._safety_timeout_seconds is not None
                and self._started_at is not None
                and time.monotonic() - self._started_at > self._safety_timeout_seconds
            ):
                self._event_bus.emit_activity(ActivityEvent(
                    agent_id=self.id,
                    event_type=ActivityEventType.SAFETY_WARNING,
                    data={
                        "warning_type": "timeout",
                        "iteration": self._iteration,
                        "timeout_seconds": self._safety_timeout_seconds,
                    },
                ))
                self.fail(
                    f"Agent timed out after {self._safety_timeout_seconds}s "
                    f"({self._iteration} iterations)"
                )
                return
            if self._iteration > self._safety_max_iterations:
                self._event_bus.emit_activity(ActivityEvent(
                    agent_id=self.id,
                    event_type=ActivityEventType.SAFETY_WARNING,
                    data={
                        "warning_type": "max_iterations",
                        "iteration": self._iteration,
                        "limit": self._safety_max_iterations,
                    },
                ))
                self.fail(
                    f"Safety limit reached ({self._safety_max_iterations} iterations)"
                )
                return

            prompt_tokens = self._usage_tracker.get_usage(self.id).get("prompt_tokens", 0)

            context_obs = (
                f"[Context Observation]\n"
                f"Turn: {self._iteration}\n"
                f"Messages in context: {len(self._messages)}\n"
                f"Estimated prompt tokens this agent: {prompt_tokens}\n"
                f"Your task: {self.task.description}\n"
            )
            self._messages.append({"role": "system", "content": context_obs})

            self._event_bus.emit_activity(ActivityEvent(
                agent_id=self.id,
                event_type=ActivityEventType.ITERATION,
                data={
                    "turn": self._iteration,
                    "messages": len(self._messages),
                    "prompt_tokens": prompt_tokens,
                },
            ))

            response = await self._llm_call_with_retry(tools)

            if response.usage:
                await self._usage_tracker.record_usage(
                    self.id,
                    prompt_tokens=response.usage.get("prompt_tokens", 0),
                    completion_tokens=response.usage.get("completion_tokens", 0),
                    message_count=len(self._messages),
                )

            ts = self._trace_store
            if ts:
                ts.record_llm_request(self.id, list(self._messages))

            if response.tool_calls:
                self._event_bus.emit_activity(ActivityEvent(
                    agent_id=self.id,
                    event_type=ActivityEventType.LLM_CALL_END,
                    data={
                        "model": response.model,
                        "prompt_tokens": response.usage.get("prompt_tokens", 0) if response.usage else 0,
                        "completion_tokens": response.usage.get("completion_tokens", 0) if response.usage else 0,
                        "tool_calls": [tc.name for tc in response.tool_calls],
                    },
                ))
                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": response.content or "",
                }
                assistant_msg["tool_calls"] = []
                results: list[dict[str, Any]] = []

                tc_info = []
                for tc in response.tool_calls:
                    tc_info.append({
                        "id": tc.id,
                        "name": tc.name,
                        "arguments": tc.arguments,
                    })
                    assistant_msg["tool_calls"].append({
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    })

                if ts:
                    ts.record_llm_response(
                        self.id, response.content, response.model,
                        response.usage, tc_info,
                    )

                has_delegates = any(tc.name == "delegate" for tc in response.tool_calls)
                if has_delegates:
                    self._deferred_delegates = []

                for tc in response.tool_calls:
                    self._event_bus.emit_activity(ActivityEvent(
                        agent_id=self.id,
                        event_type=ActivityEventType.TOOL_CALL_START,
                        data={"tool_name": tc.name, "arguments": tc.arguments},
                    ))
                    if ts:
                        ts.record_tool_call(self.id, tc.id, tc.name, tc.arguments)
                    kwargs = dict(tc.arguments)
                    if tc.name == "delegate":
                        kwargs["_tool_call_id"] = tc.id
                    result = await self._tool_registry.execute(
                        tc.name, tc.id, agent=self, **kwargs
                    )
                    if ts:
                        ts.record_tool_result(self.id, tc.id, tc.name, result.content)
                    truncated = result.content
                    if len(truncated) > MAX_TOOL_RESULT_CHARS:
                        truncated = truncated[:MAX_TOOL_RESULT_CHARS] + (
                            f"\n\n[TRUNCATED: {len(result.content) - MAX_TOOL_RESULT_CHARS} "
                            f"chars omitted from tool result ({len(result.content)} total). "
                            f"Use more specific tool parameters to reduce output size.]"
                        )
                    self._event_bus.emit_activity(ActivityEvent(
                        agent_id=self.id,
                        event_type=ActivityEventType.TOOL_CALL_END,
                        data={
                            "tool_name": tc.name,
                            "result_length": len(result.content),
                            "result_preview": result.content[:200],
                        },
                    ))
                    results.append({
                        "role": "tool",
                        "tool_call_id": result.tool_call_id,
                        "content": truncated,
                    })

                    if self.task.status in (
                        TaskStatus.completed,
                        TaskStatus.failed,
                        TaskStatus.escalated,
                    ):
                        if self._deferred_delegates is not None:
                            await self._gather_deferred_and_finalize(results)
                        self._messages.append(assistant_msg)
                        self._messages.extend(results)
                        return

                if self._deferred_delegates is not None:
                    await self._gather_deferred_and_finalize(results)

                self._messages.append(assistant_msg)
                self._messages.extend(results)

                batch_sig = tuple(
                    (tc.name, frozenset(tc.arguments.items()))
                    for tc in response.tool_calls
                )
                assert self._recent_batches is not None
                self._recent_batches.append(batch_sig)

                if (
                    len(self._recent_batches) == self.repeated_call_limit
                    and all(sig == batch_sig for sig in self._recent_batches)
                ):
                    self._event_bus.emit_activity(ActivityEvent(
                        agent_id=self.id,
                        event_type=ActivityEventType.SAFETY_WARNING,
                        data={
                            "warning_type": "repeated_calls",
                            "tool_name": response.tool_calls[0].name,
                            "repeated_count": self.repeated_call_limit,
                        },
                    ))
                    self.fail(
                        f"Repeated identical tool calls {self.repeated_call_limit} "
                        f"times in a row (tool: {response.tool_calls[0].name}). "
                        f"The provider may be stuck."
                    )
                    return
            else:
                self._event_bus.emit_activity(ActivityEvent(
                    agent_id=self.id,
                    event_type=ActivityEventType.LLM_CALL_END,
                    data={
                        "model": response.model,
                        "prompt_tokens": response.usage.get("prompt_tokens", 0) if response.usage else 0,
                        "completion_tokens": response.usage.get("completion_tokens", 0) if response.usage else 0,
                        "tool_calls": [],
                    },
                ))
                if ts:
                    ts.record_llm_response(
                        self.id, response.content, response.model, response.usage,
                    )
                content = response.content or ""
                self.report(ReportPayload(
                    task_id=self.task.id,
                    summary=content,
                ))
                return

    async def _gather_deferred_and_finalize(
        self,
        results: list[dict[str, Any]],
    ) -> None:
        if not self._deferred_delegates:
            self._deferred_delegates = None
            return
        from ..core.capabilities import _format_delegate_result

        pending = self._deferred_delegates
        self._deferred_delegates = None

        deferred_map: dict[str, Agent] = {}
        for tcid, child, task in pending:
            try:
                await task
            except asyncio.CancelledError:
                pass
            deferred_map[tcid] = child

        for r in results:
            tcid = r["tool_call_id"]
            if tcid in deferred_map:
                r["content"] = _format_delegate_result(deferred_map[tcid])

    def delegate(
        self,
        description: str,
        agent_type: str | None = None,
        role: str | None = None,
        system_prompt: str | None = None,
        **metadata: Any,
    ) -> Agent:
        child_task = Task(
            description=description,
            role=role,
            system_prompt=system_prompt,
            parent_id=self.task.id,
            metadata=metadata,
        )
        child = self._runtime.delegate(child_task, parent=self, agent_type=agent_type)
        self.children.append(child)
        return child

    def emit_activity(self, event: ActivityEvent) -> None:
        self._event_bus.emit_activity(event)

    def get_other_agent(self, agent_id: str) -> Agent | None:
        return self._runtime.get_agent(agent_id)

    def get_gitignore_filter(self) -> Any:
        return self._runtime.get_gitignore_filter()

    @property
    def generated_root(self) -> Any:
        return self._generated_root

    def report(self, payload: ReportPayload) -> None:
        self._last_report = payload
        self._runtime.deliver_report(self.id, payload)

    def request_more_budget(self, current_usage: int, requested: int, reason: str) -> None:
        req = BudgetRequest(
            task_id=self.task.id,
            current_usage=current_usage,
            requested=requested,
            reason=reason,
        )
        self._runtime.deliver_budget_request(self.id, req)

    def escalate(self, issue: str, **context: object) -> None:
        e = Escalation(task_id=self.task.id, issue=issue, context=context)
        self._runtime.deliver_escalation(self.id, e)

    def fail(self, error: str, trace: str | None = None) -> None:
        f = Failure(task_id=self.task.id, error=error, trace=trace)
        self._last_failure = f
        self._runtime.deliver_failure(self.id, f)
