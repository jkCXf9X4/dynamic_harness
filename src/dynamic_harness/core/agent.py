from __future__ import annotations

import asyncio
import json
import random
import re
import time
from collections import deque
from difflib import SequenceMatcher
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
from .telemetry import Telemetry
from ..llm.provider import LLMConfig
from .tools.registry import ToolResult
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
        repeated_recovery_attempts: int = 1,
        safety_timeout_seconds: float | None = None,
        active_turn_window: int = 50,
        stream_children: bool = False,
        # If the agent reaches `delegate_nudge_threshold` turns without having
        # delegated any work, append ONE stable reminder to split/prune/report.
        # Rare + tail-append-only so the prompt prefix (and provider cache)
        # stays contiguous. _delegate_nudge_attempts caps how many nudges fire.
        delegate_nudge_threshold: int = 8,
        delegate_nudge_attempts: int = 1,
        # Soft, non-fatal warning for *near*-identical calls (e.g. re-running a
        # path listing with slightly different head/tail/sed modifiers). Unlike
        # repeated-call detection this never fails the run — it only injects a
        # notice telling the agent to paginate / change approach.
        near_identical_threshold: int = 3,
        near_identical_window: int = 6,
        near_identical_similarity: float = 0.6,
        near_identical_tools: list[str] | None = None,
        near_identical_warning_attempts: int = 2,
        # When the agent comes within `iteration_warning_margin` iterations of
        # its `safety_max_iterations` limit, append ONE hard user message telling
        # it to wrap up: report remaining items + relevant info to its parent so
        # unfinished work can be scheduled in other tasks. Tail-append-only and
        # rare so the prompt prefix (and provider cache) stays contiguous.
        iteration_warning_margin: int = 50,
        iteration_warning_attempts: int = 1,
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
        # Remaining chances to nudge a looping agent out of its rut before
        # repeated-call detection force-fails it (0 = fail on first detection).
        self._repeated_recovery_left = repeated_recovery_attempts
        self._safety_timeout_seconds = safety_timeout_seconds
        # Hard total-request deadline per LLM call (llm.call_timeout_seconds),
        # enforced here via asyncio.wait_for. Distinct from the run-level
        # `_safety_timeout_seconds` budget; set by Runtime from config. When None
        # the call is bounded only by the provider's httpx/SDK timeout.
        self._call_timeout_seconds: float | None = None
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
        self._archived_artifact_ids: list[str] = []
        self.outcome: AgentOutcome = AgentOutcome()
        self._deferred_delegates: list[tuple[str, Agent, asyncio.Task[None]]] | None = None
        self._loop_lock = asyncio.Lock()
        # Set by Runtime.kill_agent when this agent is killed by its parent.
        # Suppresses self-heal (a killed agent must never be resurrected).
        self._killed: bool = False

        # Mid-run user input (interactive terminal / API): a queue the caller
        # fills while this agent is executing. Messages land as fresh user
        # context between turns (a working agent finishes its current turn
        # first) and an injection also unblocks a child-gather early, so a
        # parent waiting on its children reacts to the input immediately while
        # still-running children switch to fire-and-forget.
        self._inject_queue: asyncio.Queue[str] = asyncio.Queue()
        self._inject_event = asyncio.Event()

        # Streaming mode (config `agent.stream_children`): when True, delegations
        # are fire-and-forget and children settle asynchronously; the run loop is
        # re-admitted as each child completes so a parent can act on child events
        # mid-batch instead of blocking on ALL children (the default gather).
        # This holds children who have not yet surfaced into the parent's context.
        self.stream_children = stream_children
        self._stream_pending: dict[str, tuple[str, Agent, asyncio.Task[None]]] = {}

        # Registry-name of this agent's class (None for the base Agent). Used by
        # self-heal to restart a failed agent as the same agent_type.
        self.agent_type: str | None = None

        # Delegate-rarity nudge: set to True once a delegate call is observed, so
        # the reminder never fires for agents that are already delegating.
        self._has_delegated: bool = False
        self._delegate_nudge_threshold: int = max(int(delegate_nudge_threshold), 1)
        self._delegate_nudge_attempts: int = max(int(delegate_nudge_attempts), 0)
        self._delegate_nudge_left: int = self._delegate_nudge_attempts
        # Soft near-identical-warning tunables + window of recent signatures.
        # Signatures drop pagination knobs so paged reads are never flagged.
        self._near_identical_threshold: int = max(int(near_identical_threshold), 1)
        self._near_identical_window: int = max(int(near_identical_window), 2)
        self._near_identical_similarity: float = float(near_identical_similarity)
        self._near_identical_tools: tuple[str, ...] = (
            tuple(near_identical_tools) if near_identical_tools is not None else ("bash",)
        )
        self._near_identical_warning_left: int = max(int(near_identical_warning_attempts), 0)
        # Low-iteration warning: fires a hard wrap-up notice once when remaining
        # turns drop to `iteration_warning_margin` or fewer before the hard limit.
        self._iteration_warning_margin: int = max(int(iteration_warning_margin), 1)
        self._iteration_warning_attempts: int = max(int(iteration_warning_attempts), 0)
        self._iteration_warning_left: int = self._iteration_warning_attempts
        # (core sig, full sig, tool name) triples, sliding window.
        self._recent_near_identical: deque[tuple[str, str, str]] = deque(
            maxlen=self._near_identical_window
        )
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
        self._llm = runtime.provider
        self._artifact_store = runtime.artifact_store
        self._generated_root = runtime.generated_root
        # Everything the run loop treats as a *side effect* — token usage,
        # JSONL tracing, activity events, checkpoint persistence — is owned by
        # this facade, so the loop stays a pure orchestrator and stores are
        # wired in exactly one place.
        self._telemetry = Telemetry(
            agent=self,
            event_bus=runtime.event_bus,
            usage_tracker=runtime.usage_tracker,
            trace_store=runtime.trace_store,
            checkpoint_store=runtime.checkpoint_store,
        )
        self._checkpoint_notes: list[str] = []
        self._environment_info: EnvironmentInfo | None = None
        self._environment_render: str = ""
        # Set once this agent's heavyweight in-memory context has been reclaimed
        # by ``collect_garbage()``. Guards repeated collection and lets a parent
        # know its child is already just a lightweight outcome stub.
        self._context_freed: bool = False

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

    # -- garbage collection --------------------------------------------

    def collect_garbage(self) -> bool:
        """Reclaim this agent's heavyweight in-memory context once it is done.

        A terminal (reported/escalated/failed) agent is still needed by its
        parent only for its outcome state — ``last_report`` / ``_report_artifact_id``
        / ``last_failure`` / ``_iteration`` — all of which are retained. The
        large, `non-essential` buffer — the full system/user/tool message list,
        per-turn bodies, and pruning markers — is dropped so the process keeps
        only the lightweight result instead of the whole conversation.

        This loses nothing recoverable: durable state already lives in the on-disk
        checkpoint (``persist_checkpoint`` runs after every committed turn), so an
        interrupted agent can still be resumed from disk. An agent with
        un-reclaimed children is left alone (its parent may need to format them
        into a result), as is any agent that has not yet run.

        Returns True when this agent's context was reclaimed (or was already
        ``IDEMPOTENT``); False when it is not yet eligible.
        """
        if self._context_freed:
            return True
        if self.task.status not in (
            TaskStatus.completed,
            TaskStatus.failed,
            TaskStatus.escalated,
        ):
            return False
        # Do not reclaim a parent whose children are still resident: a caller
        # may still inspect a child's context (e.g. a future kill/status).
        for child in self.children:
            if not child._context_freed:
                return False
        self._context_freed = True

        self.context.messages = []
        self.context.turns = {}
        self.context.turn_order = []
        self.context.pruned = set()
        self.context.prune_markers = {}
        # Reset turn accounting so a resumed context rebuilds cleanly.
        self.context.turn_counter = 0
        # The loop-guard deques are only meaningful mid-run; drop their contents.
        self._recent_batches.clear()
        self._recent_tool_signatures.clear()
        self._recent_messages.clear()
        self._recent_delegate_targets.clear()
        self._recent_near_identical.clear()
        return True

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

        Delegates to ``Telemetry``, which concentrates checkpoint persistence
        (and its best-effort error handling) outside the run loop. Checkpoint
        writes are best-effort and NEVER fatal: a filesystem error
        (missing/permission-denied dir, disk full) must not crash or fail the
        run. We log it to the trace and emit a warning activity, then continue
        — the agent keeps working with state in memory.
        """
        self._telemetry.persist_checkpoint()

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
        self._has_delegated = False
        self._delegate_nudge_left = self._delegate_nudge_attempts
        self._iteration_warning_left = self._iteration_warning_attempts
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
                self._telemetry.event("agent_error", error=str(exc))
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
                coro = llm.generate_with_tools(msgs, tools, config=cfg)
                if self._call_timeout_seconds is not None:
                    # Hard total-deadline per call: asyncio.wait_for aborts the
                    # WHOLE request after the configured cap, unlike the httpx/SDK
                    # timeout which is an idle-per-read bound a streaming provider
                    # can stretch indefinitely. Retried like any transient failure.
                    return await asyncio.wait_for(
                        coro, timeout=self._call_timeout_seconds
                    )
                return await coro
            except Exception as e:
                last_error = e
                if not self._is_retryable(e) or attempt >= max_retries:
                    if (
                        isinstance(e, asyncio.TimeoutError)
                        and self._call_timeout_seconds is not None
                    ):
                        # The per-call deadline (llm.call_timeout_seconds) hit on
                        # every attempt. Raise distinctly from asyncio.TimeoutError
                        # so the caller's run-level budget handler
                        # (`_call_llm_with_run_budget`) doesn't misreport this as
                        # safety.timeout_seconds being exhausted.
                        raise RuntimeError(
                            f"LLM call exceeded the {self._call_timeout_seconds}s "
                            f"per-call timeout on all {max_retries + 1} attempt(s)"
                        ) from e
                    raise
                self._runtime.record_retry(self.id)
                delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
                await asyncio.sleep(delay)

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
            asyncio.TimeoutError,
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

    async def _call_llm_with_run_budget(
        self, tools: list[dict], sent: list[dict[str, Any]]
    ) -> Any | None:
        """Invoke the LLM, bounding the call by the agent's full-run budget.

        The full-run timeout (``safety.timeout_seconds``) is enforced even WHILE
        a request is in flight, so a single slow call (plus its retries) can never
        overshoot the run's wall-clock budget. Returns None when the budget was
        exhausted mid-call (the loop should stop). The per-call httpx timeout on
        the provider remains the tighter bound for a single request.
        """
        remaining = None
        if (
            self._safety_timeout_seconds is not None
            and self._started_at is not None
        ):
            remaining = self._safety_timeout_seconds - (
                time.monotonic() - self._started_at
            )
            if remaining <= 0:
                self._terminated_by_safety = True
                self.fail(
                    f"Agent timed out after {self._safety_timeout_seconds}s "
                    f"({self._iteration} iterations)"
                )
                return None
        try:
            if remaining is not None:
                return await asyncio.wait_for(
                    self._llm_call_with_retry(tools, sent), timeout=remaining
                )
            return await self._llm_call_with_retry(tools, sent)
        except asyncio.TimeoutError:
            self._terminated_by_safety = True
            self.fail(
                f"Agent timed out after {self._safety_timeout_seconds}s "
                f"({self._iteration} iterations, an LLM call exceeded the budget)"
            )
            return None

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

    async def _handle_tool_calls(self, response: Any) -> bool:
        """Execute a response's tool calls. Returns True when the agent must
        stop (a terminal status was reached while dispatching)."""
        assistant_msg: dict[str, Any] = {
            "role": "assistant",
            "content": response.content or "",
        }
        assistant_msg["tool_calls"] = []
        results: list[dict[str, Any]] = []

        for tc in response.tool_calls:
            assistant_msg["tool_calls"].append({
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": json.dumps(tc.arguments),
                },
            })

        has_delegates = any(tc.name == "delegate" for tc in response.tool_calls)
        if has_delegates:
            self._has_delegated = True
            if not self.stream_children:
                self._deferred_delegates = []

        for tc in response.tool_calls:
            self._telemetry.tool_started(tc)
            kwargs = dict(tc.arguments)
            if tc.name == "delegate":
                kwargs["_tool_call_id"] = tc.id
            try:
                result = await self._tool_registry.execute(
                    tc.name, tc.id, agent=self, **kwargs
                )
            except Exception as exc:
                # A single misbehaving tool must never take down the whole run:
                # surface the failure to the model as tool output and continue.
                self._telemetry.tool_failed(tc, exc)
                result = ToolResult(
                    tool_call_id=tc.id,
                    content=f"Error executing {tc.name}: {exc}",
                )
            content = result.content or ""
            self._telemetry.tool_finished(tc, content)
            results.append({
                "role": "tool",
                "tool_call_id": result.tool_call_id,
                "content": content,
            })

            if self.task.status in (
                TaskStatus.completed,
                TaskStatus.failed,
                TaskStatus.escalated,
            ):
                if self._stream_pending:
                    self._cancel_stream_children()
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

    @staticmethod
    def _paginationless_signature(
        name: str, arguments: dict[str, Any], exclude: set[str] | None = None
    ) -> str:
        """Signature used for *similarity* scoring: pagination knobs are dropped
        so legitimately paged reads (token_offset/token_limit changing) never
        look like a duplicated command.
        """
        skip = exclude or {"token_offset", "token_limit"}
        parts: list[str] = []
        for key in sorted(arguments):
            if key in skip:
                continue
            val = arguments[key]
            if isinstance(val, str):
                val = "_".join(val.split()).strip().lower()
            parts.append(f"{key}={json.dumps(val, sort_keys=True)}")
        return f"{name}({' '.join(parts)})"

    def _similarity(self, a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio()

    def _maybe_warn_near_identical(self, tool_calls: list[Any]) -> None:
        """Inject a *non-fatal* notice when the agent repeatedly issues
        near-identical monitored-tool calls (e.g. re-running a path listing
        with different head/tail/sed modifiers).

        This is deliberately softer than ``_check_repeated_calls``: it never
        fails the run (``near_identical_warning_attempts`` only bounds how many
        warnings refresh). Two special cases are treated as *benign*, never
        warned about: calls whose core (pagination-free) signature is identical
        — i.e. legitimate paged reads where only token_offset/token_limit
        advance — and calls against genuinely different paths.
        """
        if self._near_identical_warning_left <= 0 or not self._near_identical_tools:
            return
        if not tool_calls:
            return
        near = self._near_identical_tools
        scored: list[tuple[str, str]] = []  # (core sig, full sig)
        for tc in tool_calls:
            if tc.name in near:
                core = self._paginationless_signature(tc.name, tc.arguments)
                full = self._paginationless_signature(
                    tc.name, tc.arguments, exclude=set()
                )
                self._recent_near_identical.append((core, full, tc.name))
                scored.append((core, full))
        if not scored:
            return
        if len(self._recent_near_identical) < self._near_identical_threshold:
            return
        for core_new, full_new in scored:
            rec = list(self._recent_near_identical)
            count = sum(
                1 for core_old, full_old, _ in rec
                if core_new != core_old
                and self._similarity(full_new, full_old) >= self._near_identical_similarity
            )
            if count < self._near_identical_threshold:
                continue
            toolname = next(
                tn for c, f, tn in rec if c == core_new and f == full_new
            )
            self._near_identical_warning_left -= 1
            self._event_bus.emit_activity(ActivityEvent(
                agent_id=self.id,
                event_type=ActivityEventType.SAFETY_WARNING,
                data={
                    "warning_type": "near_identical_calls",
                    "tool_name": toolname,
                    "similar_count": count,
                    "window": len(rec),
                    "attempts_remaining": self._near_identical_warning_left,
                },
            ))
            self.context.append({
                "role": "user",
                "content": (
                    "[notice] You have issued "
                    f"{count} near-identical '{toolname}' tool calls in the last "
                    f"{len(rec)} turns (e.g. re-listing the same files with "
                    "slightly different head/tail/sort/sed modifiers). Each "
                    "returns the same material and tells you to use "
                    "token_offset/token_limit to page further. Stop re-running "
                    "these: paginate with token_offset, delegate the distinct "
                    "pieces, or move on to the next step and report / escalate / "
                    "fail. This is a warning only — it will not fail the run."
                ),
            })
            return

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
            return self._loop_detected("Repeated identical tool calls",
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
                    return self._loop_detected(
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
                return self._loop_detected(
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
                    return self._loop_detected(
                        f"Delegated {self.repeated_call_limit} times in a row "
                        f"aimed at the same target",
                        "delegate", self.repeated_call_limit)

        # Softly warn about *near*-identical (similar-not-bytes-equal) calls
        # only when no hard loop detection fired this turn, so the agent gets
        # actionable paginate/delegate guidance without a duplicate fail-nudge.
        self._maybe_warn_near_identical(response.tool_calls)

        return False

    def _loop_detected(self, message: str, tool_name: str, count: int) -> bool:
        """React to a detected loop: nudge first, fail only when the recovery
        budget is exhausted.

        On the detection, if at least one nudge remains we append a plain user
        message telling the agent it is looping and to change its actual calls,
        count a recovery attempt, and return False so the run loop continues.
        If the agent keeps looping (the deques still flag the pattern) the next
        detection consumes the remaining attempts, and only then -- or
        immediately when ``repeated_recovery_attempts=0`` -- it force-fails.
        """
        if self._repeated_recovery_left > 0:
            self._repeated_recovery_left -= 1
            self._repeated_calls_detected = True
            self._event_bus.emit_activity(ActivityEvent(
                agent_id=self.id,
                event_type=ActivityEventType.SAFETY_WARNING,
                data={
                    "warning_type": "repeated_calls",
                    "tool_name": tool_name,
                    "repeated_count": count,
                    "nudged": True,
                    "recovery_remaining": self._repeated_recovery_left,
                },
            ))
            self.context.append({
                "role": "user",
                "content": (
                    "[safety] You are looping — you have repeated "
                    f"{message.lower()} (tool: {tool_name}) {count} times in a "
                    "row. This looks stuck. Your next turn must take a genuinely "
                    "different approach or finish via report/escalate/fail. "
                    f"You have {self._repeated_recovery_left + 1} more such "
                    "warning(s) before this run is failed."
                ),
            })
            return False
        return self._fail_repeated(message, tool_name, count)

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

    def _maybe_nudge_delegation(self) -> None:
        """Emit a stable, one-off reminder when an agent never delegates.

        Scoped to agents that have reached ``_delegate_nudge_threshold`` turns
        without any ``delegate`` call. Fires at most ``_delegate_nudge_attempts``
        times and appends a fixed-text user message at the end of the context —
        never mutating a prior message — so the prompt prefix (and the provider's
        cache contiguity) is preserved after the nudge lands.
        """
        if self._has_delegated:
            return
        if self._delegate_nudge_left <= 0:
            return
        if self._iteration < self._delegate_nudge_threshold:
            return
        self._delegate_nudge_left -= 1

        note = (
            "You are N turns into this run and have not delegated any work. "
            "If your task decomposes into independent units, delegate them to "
            "fresh sub-agents in one turn and verify each by artifact summary. "
            "If the task is genuinely atomic and effectively done, prune stale "
            "committed turns to keep context flat, then report / escalate / fail "
            "instead of chaining further calls in-context."
        ).replace("N turns", f"{self._iteration} turns")

        self._event_bus.emit_activity(ActivityEvent(
            agent_id=self.id,
            event_type=ActivityEventType.SAFETY_WARNING,
            data={
                "warning_type": "delegate_reminder",
                "turn": self._iteration,
                "attempts_remaining": self._delegate_nudge_left,
            },
        ))
        self.context.append({"role": "user", "content": note})

    def _maybe_warn_iterations_low(self) -> None:
        """Inject ONE hard wrap-up message when iterations are running low.

        When remaining iterations (``safety_max_iterations - iteration``) drop to
        ``_iteration_warning_margin`` or fewer, append a fixed, assertive notice
        telling the agent to stop expanding scope, finish off what it can, and
        hand the unfinished remainder plus any relevant context to its parent so
        it can decide what to schedule in other tasks. Fires at most
        ``_iteration_warning_attempts`` times; tail-append-only so the prompt
        prefix (and the provider's cache contiguity) is preserved.
        """
        if self._iteration_warning_left <= 0:
            return
        remaining = self._safety_max_iterations - self._iteration
        if remaining > self._iteration_warning_margin:
            return
        if remaining < 0:
            remaining = 0
        self._iteration_warning_left -= 1

        note = (
            "Your iteration budget is almost exhausted: you have roughly "
            f"{remaining} iterations left before the hard limit at "
            f"{self._safety_max_iterations} (you are on iteration "
            f"{self._iteration}). Stop starting new work. Finish whatever is "
            "naturally closable right now. For anything you cannot complete, "
            "return the remaining items and all relevant intermediate context "
            "(discoveries, file paths, partial results, and what the parent "
            "would need to pick this up) to your parent, and report / escalate / "
            "fail as appropriate so the parent can decide what is reasonable to "
            "finish off in other tasks."
        )

        self._event_bus.emit_activity(ActivityEvent(
            agent_id=self.id,
            event_type=ActivityEventType.SAFETY_WARNING,
            data={
                "warning_type": "iterations_running_low",
                "iteration": self._iteration,
                "remaining": remaining,
                "limit": self._safety_max_iterations,
                "attempts_remaining": self._iteration_warning_left,
            },
        ))
        self.context.append({"role": "user", "content": note})

    def submit_input(self, message: str) -> None:
        """Queue a mid-run user message for this agent.

        A working agent finishes its current turn before the message lands as a
        fresh user turn; if the agent is instead blocked waiting on its children
        (deferred or streaming gather), the injection interrupts that wait so it
        reacts immediately (still-running children continue in the background)."""
        self._inject_queue.put_nowait(message)
        self._inject_event.set()

    def _drain_inject_input(self) -> list[str]:
        """Append all queued user messages to the live context and return them."""
        msgs: list[str] = []
        while not self._inject_queue.empty():
            msgs.append(self._inject_queue.get_nowait())
        if msgs:
            self._inject_event.clear()
            for m in msgs:
                self.context.append({"role": "user", "content": m})
        return msgs

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
            self._telemetry.turn_started(prompt_tokens)

            # Surface queued mid-run input as fresh user context before taking
            # the message snapshot, so it reaches the provider this turn.
            self._drain_inject_input()

            sent = list(self.context.messages)
            # Record the REQUEST at its actual send time (before awaiting the
            # provider), so trace latency shows the real in-flight duration.
            self._telemetry.request(sent)
            req_started = time.monotonic()
            response = await self._call_llm_with_run_budget(tools, sent)
            if response is None:
                return  # safety timeout fired mid-call
            duration_ms = (time.monotonic() - req_started) * 1000.0
            await self._telemetry.llm_call(response, sent, duration_ms)

            if response.tool_calls:
                if await self._handle_tool_calls(response):
                    self.persist_checkpoint()
                    return
                # Streaming mode: block (respecting safety) until at least one
                # delegated child settles, inject it into our context, and let the
                # parent react to that child's event before siblings finish.
                if self.stream_children and self._stream_pending:
                    if await self._harvest_streamed_child():
                        continue
            else:
                content = (response.content or "").strip()
                if not content:
                    # A response with neither tool calls nor usable text is a
                    # degenerate provider output. Fail gracefully rather than
                    # reporting an empty (misleading) success or looping forever.
                    self.fail(
                        "LLM returned an empty response "
                        "(no tool calls, no content)"
                    )
                    self.persist_checkpoint()
                    return
                self.report(ReportPayload(
                    task_id=self.task.id,
                    summary=content,
                ))
                self.persist_checkpoint()
                return
            # One-off, rare reminder: if the agent has gone past the threshold
            # without delegating, append (don't mutate) a stable nudge so the
            # next turn sees it without breaking the cached prompt prefix.
            self._maybe_nudge_delegation()
            self._maybe_warn_iterations_low()
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

        # Race the full child-gather against mid-run user input so a parent
        # blocked on its children reacts to injected input immediately, with
        # still-running children demoted to fire-and-forget (their commits and
        # artifacts still land; only the parent's in-context formatting is
        # skipped).
        inject_waiter = asyncio.create_task(self._inject_event.wait())
        try:
            done, _ = await asyncio.wait(
                [t for _, _, t in pending] + [inject_waiter],
                return_when=asyncio.FIRST_COMPLETED,
            )
        finally:
            if not inject_waiter.done():
                inject_waiter.cancel()

        if inject_waiter.done():
            # User input interrupted the wait: return without framing the
            # children's results. Still-running children continue in the
            # background; the run loop's next turn drains the queued input as a
            # fresh user message (always *after* the current turn is committed,
            # so the message ordering stays valid).
            return

        children = [child for _, child, _ in pending]
        outcomes = [await asyncio.wait_for(t, None) for _, _, t in pending]
        deferred_map: dict[str, Agent] = {}
        for (tcid, child, task), outcome in zip(pending, outcomes):
            deferred_map[tcid] = child
            if isinstance(outcome, BaseException) and not isinstance(outcome, asyncio.CancelledError):
                if not child.last_report and not child.last_failure:
                    child.fail(f"Child agent raised: {outcome}")

        for tcid, child in list(deferred_map.items()):
            if not self._runtime._has_deliverable(child):
                deferred_map[tcid] = await self._runtime._recover(child)

        for r in results:
            tcid = r["tool_call_id"]
            if tcid in deferred_map:
                r["content"] = self._format_delegate_result(deferred_map[tcid])

        # Once a child's result is folded into the parent's context, its own
        # full conversation is dead weight — reclaim it to keep the runtime lean.
        for tcid in list(deferred_map):
            child = deferred_map[tcid]
            if child is not self:
                child.collect_garbage()

    # -- streaming child events (agent.stream_children) ------------------

    async def _harvest_streamed_child(self) -> bool:
        """Wait until at least one fire-and-forget child settles, then inject its
        outcome into the parent's context and return True.

        Blocks within the parent's own wall-clock / iteration budget (loop-local
        safety check runs every second while waiting). Surfaces ONE child per
        call — the parent loop re-admits and reacts to it before siblings finish
        — which is the behavior streaming mode exists to enable. Returns False
        when there is nothing pending (or a safety limit fired while waiting)."""
        if not self._stream_pending:
            return False
        last_inject_waiter: asyncio.Task[bool] | None = None
        while True:
            if self._safety_check():
                return False
            tasks = [t for _, _, t in self._stream_pending.values()]
            inject_waiter = asyncio.create_task(self._inject_event.wait())
            if last_inject_waiter is not None and not last_inject_waiter.done():
                last_inject_waiter.cancel()
            last_inject_waiter = inject_waiter
            done, _ = await asyncio.wait(
                tasks + [inject_waiter],
                return_when=asyncio.FIRST_COMPLETED,
                timeout=1.0,
            )
            if inject_waiter.done():
                # Mid-run input while waiting on streamed children: react now.
                # The loop re-admits, drains the message into context, and calls
                # the LLM; children stay pending and surface when they settle.
                return True
            if done:
                break
        for tcid, (_, child, task) in list(self._stream_pending.items()):
            if not task.done():
                continue
            del self._stream_pending[tcid]
            if not self._runtime._has_deliverable(child):
                child = await self._runtime._recover(child)
            self.context.append({
                "role": "user",
                "content": f"[child settled]\n{self._format_delegate_result(child)}",
            })
            child.collect_garbage()
            break
        return True

    def _cancel_stream_children(self) -> None:
        """Cancel every child task that is still running (a parent terminated
        while some children are stragglers). Already-settled children are left
        in place so their commits/artifacts survive."""
        for child_tcid, (_, child, task) in list(self._stream_pending.items()):
            if not task.done():
                task.cancel()
        self._stream_pending.clear()

    # -- orchestration (delegate / report / escalate / fail) ---------------

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

    async def kill(
        self,
        agent_id: str,
        *,
        reason: str | None = None,
        recursive: bool = False,
    ) -> str:
        """Kill a child agent this agent delegated, cancelling its in-flight work
        and marking it failed. Returns a JSON summary of what was terminated."""
        target = self.get_other_agent(agent_id)
        if target is None:
            return json.dumps({"error": f"no agent found with ID {agent_id}"})
        if target.parent is not self:
            return json.dumps({
                "error": f"agent {agent_id} is not one of your direct children; "
                         "you may only kill agents you delegated",
            })
        if target.task.status in (
            TaskStatus.completed,
            TaskStatus.failed,
            TaskStatus.escalated,
        ):
            return json.dumps({
                "error": f"agent {agent_id} already {target.task.status.value}; "
                         "nothing to kill",
            })
        killed = self._runtime.kill_agent(
            target.id, reason=reason or "", recursive=recursive
        )
        salvage: dict[str, dict[str, Any]] = {}
        for kid in sorted(killed):
            a = self._runtime.get_agent(kid)
            if a is not None:
                salvage[kid] = a.runtime_snapshot()
        return json.dumps({
            "killed": sorted(killed),
            "count": len(killed),
            "status": "failed",
            "salvage": salvage,
        }, indent=2)

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

    def _context_tail(
        self, *, n_messages: int = 8, char_budget: int = 3000
    ) -> str:
        """Compact recent-activity tail from this agent's live context.

        Used by ``runtime_snapshot`` to hand a parent the partial progress a
        child made before it died/was killed, so the parent can fold that
        salvage into a fresh retry instead of starting from zero. Pulls the most
        recent assistant text and tool results (oldest→newest), bounded by a
        message count and char budget.
        """
        parts: list[str] = []
        budget = char_budget
        remaining = n_messages
        for msg in reversed(self.context.messages[1:]):  # skip system message
            if remaining <= 0 or budget <= 0:
                break
            role = msg.get("role", "")
            if role == "assistant" and msg.get("tool_calls"):
                calls = ", ".join(
                    f"{tc.get('function', {}).get('name', '?')}"
                    for tc in msg["tool_calls"]
                )
                text = f"agent_action: {calls}"
            elif role == "tool":
                text = "tool_result: " + str(msg.get("content") or "")
            else:
                text = str(msg.get("content") or "")
            text = text.strip()
            if not text:
                continue
            text = text[: budget + 200]
            parts.append(f"[{role}] {text}")
            budget -= len(text)
            remaining -= 1
        parts.reverse()
        return "\n".join(parts)

    def runtime_snapshot(self) -> dict[str, Any]:
        """Public live snapshot of this agent: status + salvageable partial work.

        A parent reads this (via the ``status`` tool, or embedded in a ``kill``
        result) to decide whether-and-how to retry a child: what already
        succeeded (done plan steps, artifact, summary) vs what was left undone
        (pending steps, recent in-context activity). ``killed``/``outcome`` let
        the parent distinguish a deliberately-killed child (retry fresh) from a
        failed one (retry carrying the failure)."""
        outcome = "running"
        if self.task.status is TaskStatus.completed:
            outcome = "completed"
        elif self._killed:
            outcome = "killed"
        elif self.task.status is TaskStatus.escalated:
            outcome = "escalated"
        elif self.task.status is TaskStatus.failed:
            outcome = "failed"

        summary = ""
        if self.last_report and self.last_report.summary:
            summary = self.last_report.summary
        elif self.last_failure and self.last_failure.error:
            summary = self.last_failure.error
        elif self.last_escalation:
            summary = self.last_escalation.issue
        if not summary:
            summary = self.latest_assistant_message()

        focus = self._focus
        return {
            "agent_id": self.id,
            "task_id": self.task.id,
            "status": self.task.status.value,
            "outcome": outcome,
            "killed": self._killed,
            "heal": {
                "diagnosis": self._runtime.heal_diagnosis(self),
                "resumes": self._runtime.get_heal_count(self.id, "resume"),
                "fresh": self._runtime.get_heal_count(self.id, "fresh"),
                # True when the runtime would re-run its automatic self-heal
                # over this agent right now (failed, or no on-disk deliverable).
                "recoverable": (
                    not self._killed
                    and self.task.status is not TaskStatus.escalated
                    and not (
                        self.last_report is not None
                        and self._runtime._has_deliverable(self)
                    )
                ),
            },
            "summary": summary[:500],
            "artifact_id": self._report_artifact_id,
            "plan": {
                "objective": focus.objective,
                "deliverable": focus.deliverable,
                "acceptance": list(focus.acceptance),
                "done": list(focus.done),
                "pending": list(focus.pending),
            },
            "checkpoint_notes": list(self._checkpoint_notes),
            "iterations": self._iteration,
            "partial_data": self._context_tail(),
        }

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

        Non-streaming (default): when the agent is mid-batch (multiple
        delegations in one turn) the child run is deferred and gathered by the
        run loop; otherwise it runs to completion here. Streaming mode: the
        child is always spawned fire-and-forget and registered in
        ``_stream_pending``; the run loop re-admits the parent as each child
        settles so it can act on child events before siblings finish. ``agent_type``
        selects a registered custom agent class; unknown names are rejected
        (never silently downgraded to the base Agent).
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
        self._runtime.set_agent_run_task(child.id, task)
        if self.stream_children:
            self._stream_pending[tool_call_id] = (tool_call_id, child, task)
            return json.dumps({"child_id": child.id, "status": "running"}, indent=2)
        if self._deferred_delegates is not None:
            self._deferred_delegates.append((tool_call_id, child, task))
            return json.dumps({"child_id": child.id, "status": "pending"}, indent=2)
        await task
        if not self._runtime._has_deliverable(child):
            child = await self._runtime._recover(child)
        result = self._format_delegate_result(child)
        child.collect_garbage()
        return result

    def report(self, payload: ReportPayload) -> None:
        if self.stream_children:
            self._cancel_stream_children()
        self.outcome.report = payload
        self._runtime.deliver_report(self.id, payload)

    async def resume_child(
        self,
        agent_id: str,
        *,
        note: str | None = None,
        strategy: str = "automatic",
    ) -> str:
        """Resume a failed (or under-delivered) child agent, returning a JSON
        summary of the attempt. Parent-facing half of the ``resume`` tool.

        Applies the same diagnosis-driven policy as the runtime's automatic
        self-heal, but with the parent's intent and a parent-supplied note:

        - ``automatic`` (default): run the blunt-vs-rot diagnosis and pick the
          layer — blunt (healthy context) resumes the SAME agent; rot (context
          is the problem: repeated calls, safety stop, huge iteration count)
          spawns a FRESH worker over the same task via ``_fresh_restart``.
        - ``resume``: force resume the same agent (only legal if not rot; a
          rotted agent is refused rather than blindly replayed).
        - ``fresh``: always spawn a fresh worker over the same task.

        Guards mirror ``kill``/``status``: only direct children, never an
        escalated child, never a *killed* child (a deliberately-killed agent
        must not be resurrected). Both layers are budgeted by the child's own
        heal counts (``self_heal.max_resumes`` / ``max_fresh_retries``); when a
        layer is exhausted the child is left as-is and the parent is told why.
        The (possibly fresh) effective agent is returned resolved as JSON.
        """
        target = self.get_other_agent(agent_id)
        if target is None:
            return json.dumps({"error": f"no agent found with ID {agent_id}"})
        if target.parent is not self:
            return json.dumps({
                "error": f"agent {agent_id} is not one of your direct children; "
                         f"you may only resume agents you delegated",
            })
        if target.task.status is TaskStatus.escalated:
            return json.dumps({
                "error": f"agent {agent_id} {target.task.status.value}; "
                         "escalations are never resumed",
            })
        if target.task.status is TaskStatus.running:
            return json.dumps({
                "error": f"agent {agent_id} is still running; nothing to resume",
            })
        if target._killed:
            return json.dumps({
                "error": f"agent {agent_id} was deliberately killed; "
                         "it cannot be resurrected — re-delegate instead",
            })
        if (
            target.last_report is not None
            and self._runtime._has_deliverable(target)
        ):
            return json.dumps({
                "agent_id": agent_id,
                "status": "already_delivered",
                "message": "child already reported with an on-disk deliverable; "
                           "nothing to resume",
            })

        strategy = (strategy or "automatic").strip().lower()
        if strategy not in ("automatic", "resume", "fresh"):
            return json.dumps({
                "error": f"unknown strategy '{strategy}'. One of: "
                         f"automatic | resume | fresh",
            })

        failures: list[str] = []
        effective: Agent = target
        diagnosis = self._runtime._diagnose(target)
        counts = self._runtime._heal_counts_for(target.id)
        note_text = note.strip() if note else ""

        def _resume_nudge(child: Agent) -> str:
            reason = (
                child.last_failure.error[:600]
                if child.last_failure
                else "the previous attempt did not produce an on-disk deliverable"
            )
            base = (
                f"A previous attempt of this task failed with: {reason}. "
                f"Resume your current work — your prior context (plan, steps, "
                f"partial results) is intact. Correct the failure; do not repeat "
                f"the same mistake — then write your deliverable(s) to disk and "
                f"finish with report()."
            )
            return f"{base}\n\nParent instruction: {note_text}" if note_text else base

        healed = False
        if strategy == "resume" and diagnosis == "rot":
            return json.dumps({
                "agent_id": agent_id,
                "status": "refused_rot",
                "diagnosis": diagnosis,
                "error": "the child's context is rotted (repeated calls / safety "
                         "stop / many iterations); force-resuming would replay the "
                         "problem. Use strategy='fresh' to restart it cleanly.",
            })

        # Layer 1: resume the same child on a blunt miss.
        if strategy in ("automatic", "resume") and (
            diagnosis == "blunt" or strategy == "resume"
        ):
            if counts["resume"] < self._runtime._self_heal_max_resumes:
                counts["resume"] += 1
                self._event_bus.emit_activity(ActivityEvent(
                    agent_id=self.id,
                    event_type=ActivityEventType.SELF_HEAL,
                    data={
                        "action": "parent_resume",
                        "child_id": target.id,
                        "diagnosis": diagnosis,
                        "attempt": counts["resume"],
                    },
                ))
                try:
                    effective = await self._runtime.resume(
                        target.id, message=_resume_nudge(target), parent=self
                    )
                except Exception as exc:
                    failures.append(f"resume errored: {exc}")
                healed = (
                    effective.last_report is not None
                    and self._runtime._has_deliverable(effective)
                )
            else:
                failures.append(
                    "resume budget exhausted "
                    f"(self_heal.max_resumes={self._runtime._self_heal_max_resumes})"
                )

        # Layer 2: fresh worker when resuming didn't heal (or rot / forced).
        if (
            not healed
            and strategy != "resume"
        ):
            if counts["fresh"] < self._runtime._self_heal_max_fresh:
                counts["fresh"] += 1
                self._event_bus.emit_activity(ActivityEvent(
                    agent_id=self.id,
                    event_type=ActivityEventType.SELF_HEAL,
                    data={
                        "action": "parent_fresh",
                        "child_id": target.id,
                        "diagnosis": diagnosis,
                        "attempt": counts["fresh"],
                    },
                ))
                fresh = self._runtime._fresh_restart(target, note=note_text or None)
                fresh_task = asyncio.create_task(fresh.run())
                self._runtime.track_agent_task(fresh_task)
                self._runtime.set_agent_run_task(fresh.id, fresh_task)
                try:
                    await fresh_task
                except Exception as exc:
                    failures.append(f"fresh worker errored: {exc}")
                healed = (
                    fresh.last_report is not None
                    and self._runtime._has_deliverable(fresh)
                )
                effective = fresh
            else:
                failures.append(
                    "fresh budget exhausted "
                    f"(self_heal.max_fresh_retries={self._runtime._self_heal_max_fresh})"
                )

        # Keep the parent's children list in sync when recovery replaced the
        # stub (disk-rebuild resume via Runtime.resume, or a fresh worker): the
        # effective agent is what the parent's status/resume will touch next.
        if effective is not target:
            for i, c in enumerate(self.children):
                if c is target:
                    self.children[i] = effective
                    break
            target.collect_garbage()

        result: dict[str, Any] = {
            "agent_id": effective.id,
            "origin_agent_id": agent_id,
            "status": effective.task.status.value,
            "diagnosis": diagnosis,
            "heal_counts": {
                "resume": counts["resume"],
                "fresh": counts["fresh"],
            },
            "healed": healed,
            "strategy": strategy,
            "summary": (
                (effective.last_report.summary[:2000]
                 if effective.last_report and effective.last_report.summary else "")
                or (effective.last_failure.error[:2000]
                    if effective.last_failure else ""),
            ),
        }
        if effective.last_report and effective._report_artifact_id:
            result["artifact_id"] = effective._report_artifact_id
        if healed:
            result["message"] = "child recovered"
        elif failures:
            result["error"] = "; ".join(failures)
        else:
            result["message"] = "no recovery applied (nothing further to do)"
        return json.dumps(result, indent=2)

    def request_more_budget(self, current_usage: int, requested: int, reason: str) -> None:
        req = BudgetRequest(
            task_id=self.task.id,
            current_usage=current_usage,
            requested=requested,
            reason=reason,
        )
        self._runtime.deliver_budget_request(self.id, req)

    def escalate(self, issue: str, **context: object) -> None:
        if self.stream_children:
            self._cancel_stream_children()
        e = Escalation(task_id=self.task.id, issue=issue, context=context)
        self.outcome.escalation = e
        self._runtime.deliver_escalation(self.id, e)

    def fail(self, error: str, trace: str | None = None) -> None:
        if self.stream_children:
            self._cancel_stream_children()
        f = Failure(task_id=self.task.id, error=error, trace=trace)
        self.outcome.failure = f
        self._telemetry.event("fail", error=error, trace=trace)
        self._runtime.deliver_failure(self.id, f)
