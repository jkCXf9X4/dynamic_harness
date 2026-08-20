from __future__ import annotations

import asyncio
import json
import random
import re
import time
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
)

from .context import AgentContext
from .prompts import AGENT_SYSTEM_PROMPT, FocusLedger, build_system_prompt, build_user_message, render_focus
from ..llm.provider import LLMConfig
from .task import (
    ActivityEvent,
    ActivityEventType,
    AgentOutcome,
    BudgetRequest,
    Escalation,
    Failure,
    ReportPayload,
    Task,
    TaskStatus,
)

if TYPE_CHECKING:
    from ..llm.provider import LLMProvider
    from .environment import EnvironmentInfo
    from .runtime import Runtime


ROT_ITERATION_THRESHOLD = 40


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
    ) -> None:
        self.id = agent_id
        self.task = task
        self.parent = parent

        # Stable per-conversation id forwarded to providers that support
        # session-pinned routing/caching (OpenRouter ``session_id``). Reused on
        # every LLM call of this agent so the prompt cache stays warm across
        # turns, instead of being invalidated by provider re-routing.
        self.session_id: str = agent_id

        self.children: list[Agent] = []

        self._system_prompt = system_prompt or task.system_prompt
        self._safety_max_iterations = safety_max_iterations
        self.repeated_call_limit = repeated_call_limit
        self._safety_timeout_seconds = safety_timeout_seconds
        self._started_at: float | None = None
        self._has_run: bool = False
        self._iteration: int = 0
        self._recent_batches: deque[list[tuple[str, str]]] = deque(
            maxlen=repeated_call_limit
        )
        self._recent_delegate_targets: deque[str] = deque(maxlen=repeated_call_limit)
        # Sliding-window of normalized individual tool calls and assistant
        # content texts, used to catch loops that *vary* slightly between turns
        # (e.g. alternating two near-identical command variants) rather than
        # repeating one batch byte-for-byte.
        self._recent_tool_signatures: deque[tuple[str, str]] = deque(
            maxlen=max(repeated_call_limit * 3, 1)
        )
        self._recent_messages: deque[str] = deque(
            maxlen=max(repeated_call_limit * 3, 1)
        )
        self._report_artifact_id: str | None = None
        self.outcome: AgentOutcome = AgentOutcome()
        self._deferred_delegates: list[tuple[str, Agent, asyncio.Task[None]]] | None = None
        self._loop_lock = asyncio.Lock()

        # Registry-name of this agent's class (None for the base Agent). Used by
        # self-heal to restart a failed agent as the same agent_type.
        self.agent_type: str | None = None
        # On-disk outputs this agent must produce (set by Runtime.run). Self-heal
        # uses them as the deliverable check when provided.
        self._expected_outputs: list[str] | None = None
        # Rot discriminators: set when the loop stopped because the *context*
        # itself is the problem (repeated identical calls / a safety limit).
        self._repeated_calls_detected: bool = False
        self._terminated_by_safety: bool = False

        # Total-token cap for this agent (None = uncapped). When set, the loop
        # force-fails once cumulative prompt+completion usage exceeds it, and the
        # cap is surfaced to the agent in its static budget guidance.
        self.max_agent_tokens: int | None = None

        self.context = AgentContext(
            active_turn_window=active_turn_window,
        )

        self._focus = FocusLedger(objective=task.description or "")

        self._runtime = runtime
        self._event_bus = runtime.event_bus
        self._tool_registry = runtime.tool_registry
        self._usage_tracker = runtime.usage_tracker
        self._llm = runtime.provider
        self._trace_store = runtime.trace_store
        self._artifact_store = runtime.artifact_store
        self._generated_root = runtime.generated_root
        self._checkpoint_store = runtime.checkpoint_store
        self._checkpoint_notes: list[str] = []
        self._environment_info: EnvironmentInfo | None = None
        self._environment_render: str = ""

    # -- outcome accessors ----------------------------------------------------

    @property
    def last_report(self) -> ReportPayload | None:
        return self.outcome.report

    @property
    def last_failure(self) -> Failure | None:
        return self.outcome.failure

    @property
    def last_escalation(self) -> Escalation | None:
        return self.outcome.escalation

    @property
    def message_count(self) -> int:
        """Number of messages currently held in this agent's context."""
        return len(self.context.messages)

    @property
    def iteration_count(self) -> int:
        """Number of LLM iterations this agent has executed."""
        return self._iteration

    def is_rot(self) -> bool:
        """True when the agent stopped because its *context* is the problem.

        Poisoned/shallow-rot indicators: repeated identical tool calls, a safety
        limit (max iterations / timeout), or so many iterations that the context
        has grown unbounded. Self-heal uses this to prefer a fresh worker over
        resuming a poisoned context.
        """
        return (
            self._repeated_calls_detected
            or self._terminated_by_safety
            or self._iteration >= ROT_ITERATION_THRESHOLD
        )

    # -- context knobs -----------------------------------------------------
    # Public tunable knobs (adjustable after construction) live on the
    # AgentContext; the run loop and tools read/write through them.

    @property
    def active_turn_window(self) -> int:
        return self.context.active_turn_window

    @active_turn_window.setter
    def active_turn_window(self, value: int) -> None:
        self.context.active_turn_window = max(int(value), 1)

    # -- focus / reminders -------------------------------------------------

    @property
    def focus(self) -> FocusLedger:
        """The agent's runtime-held focus state, re-stated every turn.

        Independent of the (prompt-optimized) system prompt; used to re-anchor
        long-running agents on objective / acceptance / deliverable.
        """
        return self._focus

    def set_focus(
        self,
        *,
        objective: str | None = None,
        acceptance: list[str] | None = None,
        deliverable: str | None = None,
        pending: list[str] | None = None,
        done: list[str] | None = None,
        pulse_interval: int | None = None,
    ) -> None:
        """Update the focus ledger that is re-stated to the agent each turn."""
        if objective is not None:
            self._focus.objective = objective
        if acceptance is not None:
            self._focus.acceptance = list(acceptance)
        if deliverable is not None:
            self._focus.deliverable = deliverable
        if pending is not None:
            self._focus.pending = list(pending)
        if done is not None:
            self._focus.done = list(done)
        if pulse_interval is not None:
            self._focus.pulse_interval = max(int(pulse_interval), 1)

    def mark_focus_done(self, item: str) -> None:
        """Record a completed scope item (removed from pending, shown as done)."""
        if item not in self._focus.done:
            self._focus.done.append(item)
        if item in self._focus.pending:
            self._focus.pending.remove(item)

    # -- planning / checkpoint persistence -------------------------------

    def persist_checkpoint(self) -> None:
        """Persist this agent's full running state to disk as structured JSON.

        Called automatically after every committed turn and whenever the agent
        plans or checkpoints, so an interrupted run can be resumed from disk.
        No-op when no checkpoint store is configured.
        """
        store = self._checkpoint_store
        if store is not None:
            store.save(self)

    def set_plan(
        self,
        *,
        steps: list[str] | None = None,
        objective: str | None = None,
        acceptance: list[str] | None = None,
        deliverable: str | None = None,
    ) -> str:
        """Record a structured plan: steps become the focus ledger's pending
        items (re-stated each turn) and are persisted in the checkpoint."""
        if objective is not None:
            self._focus.objective = objective
        if acceptance is not None:
            self._focus.acceptance = list(acceptance)
        if deliverable is not None:
            self._focus.deliverable = deliverable
        if steps is not None:
            for step in steps:
                step = str(step).strip()
                if step and step not in self._focus.done and step not in self._focus.pending:
                    self._focus.pending.append(step)
        self.persist_checkpoint()
        return f"Plan recorded: {len(steps or [])} pending step(s); progress is re-stated each turn."

    def checkpoint(self, note: str) -> str:
        """Persist current state with a milestone note, enabling crash-resume."""
        self._checkpoint_notes.append(note)
        self.persist_checkpoint()
        return f"Checkpoint saved (state on disk) — note: {note[:80]}"

    # -- LLM / environment -------------------------------------------------

    @property
    def llm(self) -> LLMProvider | None:
        return self._llm

    @property
    def guidelines(self) -> str:
        return AGENT_SYSTEM_PROMPT

    @property
    def role(self) -> str | None:
        """The agent's task role (drives tool-scoping, e.g. the orchestrator)."""
        return self.task.role

    def set_environment_info(self, info: EnvironmentInfo) -> None:
        """Inject a runtime-detected environment description shown to the agent."""
        self._environment_info = info
        self._environment_render = info.render()

    @property
    def environment_info(self) -> str:
        return self._environment_render

    async def run(self) -> None:
        llm = self.llm
        if not llm:
            self.fail("No LLM provider configured")
            return

        user_message = build_user_message(self.task.description, self.task.role)
        base = self._system_prompt or AGENT_SYSTEM_PROMPT
        system_prompt = build_system_prompt(base, role=self.task.role)
        steerage = self._build_steerage()
        if steerage:
            system_prompt = f"{system_prompt}\n\n{steerage}"
        self.context.reset(system_prompt, user_message)
        self._has_run = True
        self._iteration = 0
        self._recent_batches.clear()
        self._recent_tool_signatures.clear()
        self._recent_messages.clear()
        self._recent_delegate_targets.clear()
        self._started_at = time.monotonic()
        await self._run_guarded()

    async def _run_guarded(self) -> None:
        """Run the tool-calling loop, converting any uncaught error into a
        graceful failure so the run (and the interactive session around it)
        survives instead of crashing the process. Shared by ``run()`` and the
        interactive ``continue_with_input()`` resume path."""
        try:
            await self._run_loop()
        except asyncio.CancelledError:
            if not self.last_report and not self.last_failure:
                self.fail("Agent cancelled")
            raise
        except Exception as exc:
            if not self.last_report and not self.last_failure:
                self.fail(f"Unhandled agent error: {exc}", trace=type(exc).__name__)
            else:
                ts = self._trace_store
                if ts:
                    ts.record_event(self.id, "agent_error", error=str(exc))
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
            self.context.messages.append({"role": "user", "content": user_message})
            await self._run_guarded()

    async def _llm_call_with_retry(
        self, tools: list[dict], messages: list[dict[str, Any]] | None = None, max_retries: int = 3
    ) -> Any:
        llm = self.llm
        assert llm is not None
        msgs = messages if messages is not None else self.context.messages
        # Session-pinned config: keep every request of this conversation on the
        # same provider/cache via the agent's stable session_id.
        cfg = LLMConfig(model=llm.default_model, session_id=self.session_id)

        base_delay = 1.0
        last_error: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                return await llm.generate_with_tools(msgs, tools, config=cfg)
            except Exception as e:
                last_error = e
                if not self._is_retryable(e) or attempt >= max_retries:
                    raise
                self._runtime.record_retry(self.id)
                delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
                await asyncio.sleep(delay)

        raise last_error  # type: ignore[misc]

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        """True for transient failures (timeouts, connection drops, rate limits,
        server errors) that are safe to retry. Classifies by exception type where
        possible, falling back to message/keyword matching for unknown providers.
        """
        for cls in (
            APITimeoutError,
            APIConnectionError,
            RateLimitError,
            InternalServerError,
            httpx.TimeoutException,
            httpx.TransportError,
        ):
            if isinstance(exc, cls):
                return True
        # Server-side status errors (5xx) are transient regardless of message.
        if isinstance(exc, APIStatusError):
            status = getattr(exc, "status_code", None)
            if status is not None and 500 <= status < 600:
                return True

        error_str = str(exc).lower()
        return any(
            keyword in error_str
            for keyword in (
                "rate_limit", "rate limit", "429", "too many requests",
                "server_error", "500", "502", "503", "504",
                "timeout", "timed out", "temporary", "connection", "network",
                "overloaded", "capacity",
                "expecting value", "jsondecode", "anticipate_processing_error",
            )
        )

    # -- turn / context helpers (delegate to context) ---------------------

    def _format_delegate_result(self, child: Agent) -> str:
        status = child.task.status.value
        self._event_bus.emit_activity(ActivityEvent(
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

        if child.last_report:
            r = child.last_report
            result["summary"] = r.summary[:2000] if r.summary else ""
            if child._report_artifact_id:
                result["artifact_id"] = child._report_artifact_id
            if r.artifact_ids:
                result["artifact_ids"] = r.artifact_ids
            if r.full_report:
                result["full_report"] = r.full_report
            if r.technical_summary:
                result["technical_summary"] = r.technical_summary
            if r.confidence is not None:
                result["confidence"] = r.confidence

        if child.last_failure:
            result["failure"] = child.last_failure.error[:500]

        return json.dumps(result, indent=2)

    # -- run loop ---------------------------------------------------------

    def _safety_check(self) -> bool:
        """Return True when a safety limit was hit and the loop must stop."""
        if (
            self._safety_timeout_seconds is not None
            and self._started_at is not None
            and time.monotonic() - self._started_at > self._safety_timeout_seconds
        ):
            self._terminated_by_safety = True
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
            self._terminated_by_safety = True
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
        if self.max_agent_tokens:
            current = self._runtime.get_usage(self.id).get("total_tokens", 0)
            if current > self.max_agent_tokens:
                self._terminated_by_safety = True
                self._event_bus.emit_activity(ActivityEvent(
                    agent_id=self.id,
                    event_type=ActivityEventType.SAFETY_WARNING,
                    data={
                        "warning_type": "max_token_budget",
                        "used": current,
                        "limit": self.max_agent_tokens,
                    },
                ))
                self.fail(
                    f"Token budget exceeded: {current} > {self.max_agent_tokens} "
                    f"total tokens. This agent stopped to contain cost."
                )
                return True
        return False

    def _build_steerage(self) -> str:
        """Static, cache-friendly context block folded into the system prompt.

        Environment and focus reminders are stable for the life of a run, so
        baking them into the leading system message (once, at reset) rather than
        emitting a changing per-turn observation message keeps the conversation
        prefix byte-identical. That byte-identity is what lets the provider's
        prompt cache extend across the whole history — a per-turn observation
        message was empirically shown to zero out the cache entirely.
        """
        blocks: list[str] = []
        focus_text = render_focus(self._focus, iteration=1)
        if focus_text:
            blocks.append(focus_text)
        if self.max_agent_tokens:
            blocks.append(
                f"[Budget] This agent may use at most {self.max_agent_tokens} total "
                f"tokens (prompt + completion) before the run is stopped. Track your "
                f"live spend and messages with the usage tool; to stay lean, "
                f"delegate or prune stale turns instead of chaining calls in-context."
            )
        if self.environment_info:
            blocks.append(self.environment_info)
        return "\n\n".join(blocks)

    def _emit_iteration(self, prompt_tokens: int) -> None:
        self._event_bus.emit_activity(ActivityEvent(
            agent_id=self.id,
            event_type=ActivityEventType.ITERATION,
            data={
                "turn": self._iteration,
                "messages": len(self.context.messages),
                "prompt_tokens": prompt_tokens,
            },
        ))

    async def _record_usage_and_trace(self, response: Any, sent_messages: list[dict[str, Any]]) -> None:
        if response.usage:
            await self._usage_tracker.record_usage(
                self.id,
                prompt_tokens=response.usage.get("prompt_tokens", 0),
                completion_tokens=response.usage.get("completion_tokens", 0),
                cached_tokens=response.usage.get("cached_tokens", 0),
                message_count=len(sent_messages),
            )
        ts = self._trace_store
        if ts:
            ts.record_llm_request(self.id, list(sent_messages))

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
                self.context.commit_turn(assistant_msg, results)
                return True

        if self._deferred_delegates is not None:
            await self._gather_deferred_and_finalize(results)

        self.context.commit_turn(assistant_msg, results)
        return self._check_repeated_calls(response)

    @staticmethod
    def _delegate_target_signature(arguments: dict[str, Any]) -> str:
        """Normalized key for a delegate call, keyed on the referenced path(s).

        Catches the failure mode where an orchestrator re-reads *the same file*
        by spinning a fresh sub-agent each time with superficially different
        wording (e.g. 'read X verbatim' → 'read X from offset N' → ...).
        """
        description = str(arguments.get("description", ""))
        paths = sorted(set(
            p for p in re.findall(r"[\w./\-]+\.(?:md|txt|py|json|yaml|yml|toml|log)", description)
        ))
        return "|".join(paths) if paths else description.strip()

    @staticmethod
    def _normalize_tool_signature(name: str, arguments: dict[str, Any]) -> str:
        """Canonical, whitespace-insensitive key for a single tool call.

        Small stylistic variation (quote style, padding, casing, shell
        chaining) is folded away so a genuinely stuck loop is not hidden by
        the model nudging the wording/format of an identical command.
        """
        parts: list[str] = []
        for key in sorted(arguments):
            val = arguments[key]
            if isinstance(val, str):
                val = "_".join(val.split()).strip().lower()
            parts.append(f"{key}={json.dumps(val, sort_keys=True)}")
        return f"{name}({' '.join(parts)})"

    def _check_repeated_calls(self, response: Any) -> bool:
        """Return True when repeated calls were detected (loop stops).

        Detects three loop shapes:
          1. ``repeated_call_limit`` consecutive *byte-identical* batches.
          2. The same normalized tool call occurring ``limit`` times within a
             small sliding window -- catches alternation between two near-
             identical command variants (e.g. grep A vs grep A+B).
          3. Repeated delegation aimed at the same target path.
        """
        batch_sig = tuple(
            (tc.name, json.dumps(tc.arguments, sort_keys=True))
            for tc in response.tool_calls
        )
        self._recent_batches.append(batch_sig)

        if (
            len(self._recent_batches) == self.repeated_call_limit
            and all(sig == batch_sig for sig in self._recent_batches)
        ):
            return self._fail_repeated("Repeated identical tool calls",
                                       response.tool_calls[0].name,
                                       self.repeated_call_limit)

        # Sliding-window frequency check over individual normalized calls.
        # Any tool name+args occurring `limit` times within the last
        # (limit*2) calls is treated as a loop, even if batches interleave
        # with a sibling variant.
        limit = self.repeated_call_limit
        for tc in response.tool_calls:
            sig = self._normalize_tool_signature(tc.name, tc.arguments)
            self._recent_tool_signatures.append(sig)
        if len(self._recent_tool_signatures) >= limit:
            recent = list(self._recent_tool_signatures)
            window = recent[-limit * 2:]
            for sig in set(window):
                if window.count(sig) >= limit:
                    return self._fail_repeated(
                        f"Tool call '{sig}' appeared {limit} times in the "
                        f"last {limit * 2} calls",
                        response.tool_calls[-1].name, limit)

        # Identical assistant text repeated many times is also a stuck signal,
        # regardless of how the tool arguments vary around it.
        if response.content:
            self._recent_messages.append(response.content.strip())
        if len(self._recent_messages) >= limit * 2:
            recent_msgs = list(self._recent_messages)
            if recent_msgs[-limit:] == [recent_msgs[-1]] * limit:
                return self._fail_repeated(
                    "Repeated identical assistant responses", "LLM", limit)

        # Semantic guard: many consecutive delegate calls aimed at the *same*
        # target (path) signal a verification loop, even if the wording varies.
        for tc in response.tool_calls:
            if tc.name == "delegate":
                sig = self._delegate_target_signature(tc.arguments)
                self._recent_delegate_targets.append(sig)
                if (
                    len(self._recent_delegate_targets) == self.repeated_call_limit
                    and len(set(self._recent_delegate_targets)) == 1
                ):
                    return self._fail_repeated(
                        f"Delegated {self.repeated_call_limit} times in a row "
                        f"aimed at the same target",
                        "delegate", self.repeated_call_limit)

        return False

    def _fail_repeated(self, message: str, tool_name: str, count: int) -> bool:
        self._repeated_calls_detected = True
        self._event_bus.emit_activity(ActivityEvent(
            agent_id=self.id,
            event_type=ActivityEventType.SAFETY_WARNING,
            data={
                "warning_type": "repeated_calls",
                "tool_name": tool_name,
                "repeated_count": count,
            },
        ))
        self.fail(
            f"{message} {count} times in a row (tool: {tool_name}). "
            f"The provider may be stuck. Change strategy or stop."
        )
        return True

    async def _run_loop(self) -> None:
        tools = self._tool_registry.openai_schemas(role=self.task.role)

        while True:
            self._iteration += 1
            if self._safety_check():
                return
            # Persist state before each LLM call so a crash mid-turn still leaves
            # every committed turn (and the plan) recoverable from disk.
            self.persist_checkpoint()

            prompt_tokens = self.context.estimate_prompt_tokens()
            self._emit_iteration(prompt_tokens)

            sent = list(self.context.messages)
            response = await self._llm_call_with_retry(tools, sent)
            await self._record_usage_and_trace(response, sent)

            if response.tool_calls:
                if await self._handle_tool_calls(response):
                    self.persist_checkpoint()
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
                self.persist_checkpoint()
                return
            self.persist_checkpoint()

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
                if not child.last_report and not child.last_failure:
                    child.fail(f"Child agent raised: {outcome}")

        # Self-heal: recover failed children (resume-once or fresh worker) so the
        # parent format step below reflects the healed result, not the failure.
        # Also heal a child that *completed* without an on-disk deliverable
        # (prose-only report) — the exact case self-healing Layer 1 targets.
        for tcid, child in list(deferred_map.items()):
            if not self._runtime._has_deliverable(child):
                deferred_map[tcid] = await self._runtime._recover(child)

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

    @property
    def artifact_store(self) -> Any:
        return self._artifact_store

    def latest_assistant_message(self) -> str:
        """Last assistant text message in this agent's context (empty if none)."""
        for msg in reversed(self.context.messages):
            if msg.get("role") == "assistant" and msg.get("content"):
                return msg["content"][:500]
        return ""

    async def run_delegate_tool(
        self,
        description: str,
        *,
        role: str | None = None,
        system_prompt: str | None = None,
        agent_type: str | None = None,
        tool_call_id: str = "",
    ) -> str:
        """Create + run a sub-agent on behalf of the ``delegate`` tool.

        When the agent is mid-batch (multiple delegations in one turn) the child
        run is deferred and gathered by the run loop; otherwise it runs to
        completion here. ``agent_type`` selects a registered custom agent class;
        unknown names are rejected (never silently downgraded to the base Agent).
        """
        if agent_type and not self._runtime.has_agent_class(agent_type):
            known = self._runtime.registered_agent_classes()
            return json.dumps({
                "error": f"unknown agent_type '{agent_type}'. "
                        f"Registered custom classes: {known or '(none)'}",
            }, indent=2)
        child = self.delegate(description, agent_type=agent_type, role=role, system_prompt=system_prompt)
        self.emit_activity(ActivityEvent(
            agent_id=self.id,
            event_type=ActivityEventType.DELEGATION_START,
            data={
                "child_id": child.id,
                "description": description[:200],
                "role": role,
            },
        ))
        task = asyncio.create_task(child.run())
        self._runtime.track_agent_task(task)
        if self._deferred_delegates is not None:
            self._deferred_delegates.append((tool_call_id, child, task))
            return json.dumps({"child_id": child.id, "status": "pending"}, indent=2)
        await task
        if not self._runtime._has_deliverable(child):
            child = await self._runtime._recover(child)
        return self._format_delegate_result(child)

    def report(self, payload: ReportPayload) -> None:
        self.outcome.report = payload
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
        self.outcome.escalation = e
        self._runtime.deliver_escalation(self.id, e)

    def fail(self, error: str, trace: str | None = None) -> None:
        f = Failure(task_id=self.task.id, error=error, trace=trace)
        self.outcome.failure = f
        ts = self._trace_store
        if ts:
            ts.record_event(self.id, "fail", error=error, trace=trace)
        self._runtime.deliver_failure(self.id, f)
