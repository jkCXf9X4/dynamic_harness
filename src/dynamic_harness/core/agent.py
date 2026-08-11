from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .context import AgentContext
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
        active_turn_window: int = 50,
        max_pruned_retained: int = 100,
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
        self._has_run: bool = False
        self._iteration: int = 0
        self._recent_batches: deque[list[tuple[str, str]]] | None = None
        self._last_report: ReportPayload | None = None
        self._last_failure: Failure | None = None
        self._deferred_delegates: list[tuple[str, Agent, asyncio.Task[None]]] | None = None
        self._loop_lock = asyncio.Lock()

        self.context = AgentContext(
            active_turn_window=active_turn_window,
            max_pruned_retained=max_pruned_retained,
        )

        self._runtime = runtime
        self._event_bus = runtime.event_bus
        self._tool_registry = runtime.tool_registry
        self._usage_tracker = runtime.usage_tracker
        self._llm = runtime.provider
        self._trace_store = runtime.trace_store
        self._artifact_store = runtime.artifact_store
        self._generated_root = runtime.generated_root

    # -- context proxy accessors -----------------------------------------
    # Public knobs (tunable after construction) live on the AgentContext;
    # the run loop, tools, and tests all read/write through these.

    @property
    def active_turn_window(self) -> int:
        return self.context.active_turn_window

    @active_turn_window.setter
    def active_turn_window(self, value: int) -> None:
        self.context.active_turn_window = max(int(value), 1)

    @property
    def max_pruned_retained(self) -> int:
        return self.context.max_pruned_retained

    @max_pruned_retained.setter
    def max_pruned_retained(self, value: int) -> None:
        self.context.max_pruned_retained = max(int(value), 0)

    @property
    def _messages(self) -> list[dict[str, Any]]:
        return self.context.messages

    @_messages.setter
    def _messages(self, value: list[dict[str, Any]]) -> None:
        self.context.messages = value

    @property
    def _turn_counter(self) -> int:
        return self.context.turn_counter

    @property
    def _turn_order(self) -> list[str]:
        return self.context.turn_order

    @property
    def _turns(self) -> dict[str, list[dict[str, Any]]]:
        return self.context.turns

    @property
    def _pruned(self) -> set[str]:
        return self.context.pruned

    @property
    def _prune_markers(self) -> dict[str, dict[str, Any]]:
        return self.context.prune_markers

    @property
    def _in_flight_prune(self) -> set[str]:
        return self.context.in_flight_prune

    # -- LLM / environment -------------------------------------------------

    @property
    def llm(self) -> LLMProvider | None:
        return self._llm

    @property
    def guidelines(self) -> str:
        return AGENT_SYSTEM_PROMPT

    @property
    def environment_info(self) -> str:
        return (
            "[Environment]\n"
            "Python 3.11 | pip NOT available | pytest NOT installed\n"
            "Working dir: project root with pyproject.toml\n"
            "Packages: pydantic, openai, dotenv, pyyaml, httpx, rich, textual, pathspec\n"
            ".optimize_benchmarks/ exists — do not recreate\n"
            "Git available | os: linux\n"
            "Do NOT attempt to install packages — use python3 -c for inline code\n"
        )

    async def run(self) -> None:
        llm = self.llm
        if not llm:
            self.fail("No LLM provider configured")
            return

        user_message = self.task.description
        if self.task.role:
            user_message = f"[ROLE] {self.task.role}\n\n[TASK] {self.task.description}"
        self.context.reset(self._system_prompt or AGENT_SYSTEM_PROMPT, user_message)
        self._has_run = True
        self._iteration = 0
        self._recent_batches = deque(maxlen=self.repeated_call_limit)
        self._started_at = time.monotonic()
        try:
            await self._run_loop()
        except asyncio.CancelledError:
            if not self._last_report and not self._last_failure:
                self.fail("Agent cancelled")
            raise
        except Exception as exc:
            if not self._last_report and not self._last_failure:
                self.fail(f"Unhandled agent error: {exc}")
            self._event_bus.emit_activity(ActivityEvent(
                agent_id=self.id,
                event_type=ActivityEventType.SAFETY_WARNING,
                data={"warning_type": "agent_error", "error": str(exc)},
            ))

    async def continue_with_input(self, user_message: str) -> None:
        async with self._loop_lock:
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
                        "expecting value", "jsondecode", "anticipate_processing_error",
                    )
                )
                if not is_retryable or attempt >= max_retries:
                    raise
                self._runtime.record_retry(self.id)
                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)

        raise last_error  # type: ignore[misc]

    # -- turn / context helpers (delegate to context) ---------------------

    def _commit_turn(
        self,
        assistant_msg: dict[str, Any],
        results: list[dict[str, Any]],
    ) -> str:
        return self.context.commit_turn(assistant_msg, results)

    def _make_prune_marker(self, pid: str) -> str:
        return self.context.make_prune_marker(pid)

    def _turn_token_estimate(self, pid: str) -> int:
        return self.context.turn_token_estimate(pid)

    def _turn_tool_names(self, pid: str) -> str:
        return self.context.turn_tool_names(pid)

    def active_turn_ids(self) -> list[str]:
        return self.context.active_turn_ids()

    def evict_pruned_overflow(self) -> list[str]:
        return self.context.evict_overflow()

    def _format_delegate_result(self, child: Agent) -> str:
        status = child.task.status.value
        child._runtime.emit_activity(ActivityEvent(
            agent_id=child.parent.id if child.parent else "",
            event_type=ActivityEventType.DELEGATION_END,
            data={
                "child_id": child.id,
                "status": status,
            },
        ))
        result: dict[str, Any] = {
            "child_id": child.id,
            "status": status,
        }

        if child._last_report:
            r = child._last_report
            result["summary"] = r.summary[:500]
            if r.artifact_ids:
                result["artifact_ids"] = r.artifact_ids
            if r.confidence is not None:
                result["confidence"] = r.confidence

        if child._last_failure:
            result["failure"] = child._last_failure.error[:500]

        return json.dumps(result, indent=2)

    # -- run loop ---------------------------------------------------------

    def _safety_check(self) -> bool:
        """Return True when a safety limit was hit and the loop must stop."""
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
            return True
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
            return True
        return False

    def _context_observation(self, prompt_tokens: int) -> str:
        active_turns = self.active_turn_ids()
        if active_turns:
            turn_map = " · ".join(
                f"{pid}:{self._turn_tool_names(pid)}"
                f"(~{self._turn_token_estimate(pid)}tk)"
                for pid in active_turns
            )
            total_active = sum(
                self._turn_token_estimate(pid) for pid in active_turns
            )
        else:
            turn_map = "none"
            total_active = 0
        next_turn = f"t{self._turn_counter}"
        return (
            f"[Context Observation]\n"
            f"Turn: {self._iteration}\n"
            f"Messages in context: {len(self._messages)}\n"
            f"Estimated prompt tokens this agent: {prompt_tokens}\n"
            f"Active turn tokens: {total_active} (prune stale turns to cut this)\n"
            f"Recent committed turns (prune_id:tools~tokens): {turn_map}\n"
            f"Your next turn will commit as prune_id: {next_turn}.\n"
            f"Prune turns whose results are already on disk using "
            f"prune(prune_ids=['tN', ...]); the costliest turns save the most.\n"
            f"Your task: {self.task.description}\n"
            f"{self.environment_info}"
        )

    def _emit_iteration(self, prompt_tokens: int) -> None:
        self._event_bus.emit_activity(ActivityEvent(
            agent_id=self.id,
            event_type=ActivityEventType.ITERATION,
            data={
                "turn": self._iteration,
                "messages": len(self._messages),
                "prompt_tokens": prompt_tokens,
            },
        ))

    async def _record_usage_and_trace(self, response: Any) -> None:
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

    def _emit_llm_end(self, response: Any, tool_names: list[str]) -> None:
        self._event_bus.emit_activity(ActivityEvent(
            agent_id=self.id,
            event_type=ActivityEventType.LLM_CALL_END,
            data={
                "model": response.model,
                "prompt_tokens": response.usage.get("prompt_tokens", 0) if response.usage else 0,
                "completion_tokens": response.usage.get("completion_tokens", 0) if response.usage else 0,
                "tool_calls": tool_names,
            },
        ))

    async def _handle_tool_calls(self, response: Any) -> bool:
        """Execute a response's tool calls. Returns True when the agent must
        stop (a terminal status was reached while dispatching)."""
        ts = self._trace_store
        self._emit_llm_end(response, [tc.name for tc in response.tool_calls])

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
                self._commit_turn(assistant_msg, results)
                return True

        if self._deferred_delegates is not None:
            await self._gather_deferred_and_finalize(results)

        self._commit_turn(assistant_msg, results)
        return self._check_repeated_calls(response)

    def _check_repeated_calls(self, response: Any) -> bool:
        """Return True when repeated identical calls were detected (loop stops)."""
        batch_sig = tuple(
            (tc.name, json.dumps(tc.arguments, sort_keys=True))
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
            return True
        return False

    async def _run_loop(self) -> None:
        tools = self._tool_registry.openai_schemas()

        while True:
            self._iteration += 1
            if self._safety_check():
                return

            prompt_tokens = self._usage_tracker.get_usage(self.id).get("prompt_tokens", 0)
            self._messages.append({"role": "system", "content": self._context_observation(prompt_tokens)})
            self._emit_iteration(prompt_tokens)

            response = await self._llm_call_with_retry(tools)
            await self._record_usage_and_trace(response)

            if response.tool_calls:
                if await self._handle_tool_calls(response):
                    return
            else:
                self._emit_llm_end(response, [])
                ts = self._trace_store
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

        pending = self._deferred_delegates
        self._deferred_delegates = None

        children = [child for _, child, _ in pending]
        outcomes = await asyncio.gather(
            *(task for _, _, task in pending),
            return_exceptions=True,
        )

        deferred_map: dict[str, Agent] = {}
        for (tcid, child, _), outcome in zip(pending, outcomes):
            deferred_map[tcid] = child
            if isinstance(outcome, BaseException) and not isinstance(outcome, asyncio.CancelledError):
                if not child._last_report and not child._last_failure:
                    child.fail(f"Child agent raised: {outcome}")

        for r in results:
            tcid = r["tool_call_id"]
            if tcid in deferred_map:
                r["content"] = self._format_delegate_result(deferred_map[tcid])

    # -- orchestration (delegate / report / escalate / fail) --------------

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

    async def workspace_lock(self, path) -> asyncio.Lock:
        """Per-path lock serializing concurrent writes to the same file."""
        return await self._runtime.acquire_path_lock(str(path))

    def repo_lock(self) -> asyncio.Lock:
        """Global lock serializing repo-mutating operations across agents."""
        return self._runtime.repo_lock()

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
