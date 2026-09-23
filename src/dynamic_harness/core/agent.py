from __future__ import annotations

import asyncio
import json
import random
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

from .context import AgentContext
from .policies.interface import (
    Observation,
    PromptInjection,
    ReactivePolicy,
    ReactivePolicyRegistry,
)
from .policies.loop_guard import (
    LoopAction,
    LoopGuard,
    bash_family,
    bash_read_regions,
    loop_action_to_injection,
    normalize_tool_signature,
    paginationless_signature,
    regions_overlap,
    similarity,
)
from .policies.retry import RetryPolicy
from .policies.budget import TimeoutPolicy, TokenBudgetPolicy
from .policies.heal import ResumePlanner
from .policies.nudge import NudgePolicy
from .policies.brief import BriefPolicy
from .policies.permissions import ToolPermissionPolicy
from .policies.spawn import SpawnWarningPolicy
from .prompts import AGENT_SYSTEM_PROMPT, FocusLedger, build_brief_block, build_system_prompt, build_user_message, render_focus
from .result_store import ResultStore
from .spawn_limits import DelegationLimit, delegate_target_signature
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

# File-like token used by the bash near-identical read-region parser.
_PATH_TOKEN = re.compile(
    r"([\w./~@-]+\.(?:cpp|hpp|c|h|md|json|txt|py|toml|csv|log|ya?ml|ini|rc|in)|"
    r"(?:\./)?[\w./~@-]+\.dynamic-harness/[\w./~@-]+)"
)


def progress_summary_block(
    *,
    objective: str = "",
    deliverable: str = "",
    acceptance: list[str] | None = None,
    pending: list[str] | None = None,
    done: list[str] | None = None,
    checkpoint_notes: list[str] | None = None,
) -> str:
    """Render an agent's documented progress for injection into a resume nudge.

    This is the deterministic record of "what has been done" that a resumed
    agent (or a fresh worker inheriting it) should start from: the residual
    plan, what is already marked done, and the checkpoint milestones recorded
    along the way. It keeps the agent from having to re-derive its own progress
    from raw prior turns after a failure.
    """
    lines = ["[Your documented progress, recorded before the interruption]"]
    if objective:
        lines.append(f"Objective: {objective}")
    if deliverable:
        lines.append(f"Deliverable: {deliverable}")
    if done:
        lines.append("Plan steps already done: " + "; ".join(done))
    if pending:
        lines.append("Plan steps remaining: " + "; ".join(pending))
    if acceptance:
        lines.append("Acceptance: " + "; ".join(acceptance))
    notes = list(checkpoint_notes or [])
    if notes:
        lines.append("Milestones recorded so far:")
        lines += [f"  - {n}" for n in notes[-12:]]
    return "\n".join(lines)


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
        repeated_recovery_attempts: int = 2,
        # Read-only monitoring tools excluded from repeated-call loop detection
        # (status / usage). These are cheap live observations whose outputs
        # change as state changes — a parent polling its running children is
        # waiting, not looping. A turn composed ONLY of these tools is not
        # counted toward loop detection at all.
        repeated_call_exempt_tools: list[str] | None = None,
        safety_timeout_seconds: float | None = None,
        active_turn_window: int = 50,
        stream_children: bool = False,
        # If the agent reaches `delegate_nudge_threshold` turns without having
        # delegated any work, append ONE stable reminder to split/prune/report.
        # Rare + tail-append-only so the prompt prefix (and provider cache)
        # stays contiguous. _delegate_nudge_attempts caps how many nudges fire.
        delegate_nudge_threshold: int = 8,
        delegate_nudge_attempts: int = 1,
        # One-off notice when a delegate() call omits the mission-command intent
        # dimension (intent/end_state) — the parent should brief the WHY, not
        # just the WHAT. Tail-append-only and rare (budgeted) so the prompt
        # prefix (and provider cache) stays contiguous.
        brief_nudge_attempts: int = 1,
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
        # Repeated-call / near-identical detection lives in a composable
        # LoopGuard policy object (core/policies/loop_guard.py). The agent
        # exposes compatibility attributes below that forward to it.
        self._loop_guard = LoopGuard(
            repeated_call_limit=repeated_call_limit,
            repeated_call_exempt_tools=repeated_call_exempt_tools,
            repeated_recovery_attempts=repeated_recovery_attempts,
            near_identical_threshold=near_identical_threshold,
            near_identical_window=near_identical_window,
            near_identical_similarity=near_identical_similarity,
            near_identical_tools=near_identical_tools,
            near_identical_warning_attempts=near_identical_warning_attempts,
        )
        # The metric-reactive policies behind the post-turn directive pass
        # (core/policies/interface.py). Each implements ``ReactivePolicy``:
        # it observes a live ``Observation`` and returns ``PromptInjection``(s)
        # the shared applier injects into the context. A host can add (or
        # replace) policies on ``reactive_policies`` without touching the loop.
        self._nudge_policy = NudgePolicy(
            delegate_nudge_threshold=delegate_nudge_threshold,
            delegate_nudge_attempts=delegate_nudge_attempts,
            iteration_warning_margin=iteration_warning_margin,
            iteration_warning_attempts=iteration_warning_attempts,
            safety_max_iterations=safety_max_iterations,
        )
        self._brief_policy = BriefPolicy(brief_nudge_attempts=brief_nudge_attempts)
        # Per-agent near-cap warning budget; the shared SpawnPolicy wordings
        # come from the runtime. Runtime.delegate() sets the starting budget.
        self._spawn_warning_policy = SpawnWarningPolicy(
            runtime.spawn_policy, warning_attempts=0
        )
        # The post-turn reactive registry. LoopGuard is NOT evaluated here: loop
        # detection runs at commit time (right after a tool turn) so it also
        # fires on stream-harvest iterations that `continue` past the tail.
        self.reactive_policies = ReactivePolicyRegistry(
            self._nudge_policy,
            self._brief_policy,
            self._spawn_warning_policy,
        )
        self._safety_timeout_seconds = safety_timeout_seconds
        # Hard total-request deadline per LLM call (llm.call_timeout_seconds),
        # enforced here via asyncio.wait_for. Distinct from the run-level
        # `_safety_timeout_seconds` budget; set by Runtime from config. When None
        # the call is bounded only by the provider's httpx/SDK timeout.
        self._call_timeout_seconds: float | None = None
        # LLM call retry policy (llm.* in harness.json, overridden by
        # Runtime.delegate()). Rate limits (429 / engine_overloaded) get more
        # attempts and a longer backoff than generic transient errors, and —
        # when fallback_on_rate_limit is set — retries drop the session-pinned
        # provider so OpenRouter can route around the overloaded upstream pool.
        self.retry_max_attempts: int = 4
        self.rate_limit_max_attempts: int = 6
        self.retry_base_delay_seconds: float = 1.0
        self.retry_max_delay_seconds: float = 30.0
        self.retry_jitter_seconds: float = 0.5
        self.rate_limit_backoff_multiplier: float = 3.0
        self.fallback_on_rate_limit: bool = True
        self._started_at: float | None = None
        self._has_run: bool = False
        self._iteration: int = 0
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
        # parent waiting on its children reacts to the input immediately. The
        # interrupted children are NOT dropped: still-running ones stay
        # registered and are re-gathered (their results fold into the parent's
        # context) in a later turn, so answering the user never costs the
        # delegation.
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
        # Low-iteration warning: fires a hard wrap-up notice once when remaining
        # turns drop to `iteration_warning_margin` or fewer before the hard limit.
        # The nudge thresholds / attempt budgets now live on `self._nudge_policy`;
        # the old private names are kept as forwarding properties below.
        # On-disk outputs this agent must produce (set by Runtime.run). Self-heal
        # uses them as the deliverable check when provided.
        self._expected_outputs: list[str] | None = None
        # Rot discriminators: set when the loop stopped because the *context*
        # itself is the problem (repeated identical calls / a safety limit).
        # `_repeated_calls_detected` now lives on the LoopGuard (exposed below).
        self._terminated_by_safety: bool = False
        # True only for a WALL-CLOCK timeout (`safety.timeout_seconds` or the
        # run budget fired). Distinct from other safety stops: a timeout is a
        # budget exhaustion, not a poisoned context, so it is never self-healed
        # and stays resumable by the parent (blunt, not rot).
        self._timed_out: bool = False

        # Total-token cap for this agent (None = uncapped). When set, the loop
        # force-fails once cumulative prompt+completion usage exceeds it, and the
        # cap is surfaced to the agent in its static budget guidance.
        self.max_agent_tokens: int | None = None

        # Spawn-cap accounting, populated by Runtime.delegate():
        # - `_depth`        : this agent's tree depth (root = 0).
        # - `_spawn_ledger` : per-lineage share re-delegation counter (the same
        #   object is inherited by every descendant, so the same-target cap is
        #   lineage-scoped and survives self-heal restarts).
        # - `_spawn_warning_left` : budget for near-cap [notice] injections
        #   (forwarded to the per-agent SpawnWarningPolicy).
        self._depth: int = 0
        self._spawn_ledger: Any = None
        self._spawn_warning_left = 0  # forwards to _spawn_warning_policy

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
        self._reference_root = runtime.reference_root
        # Bounded, in-memory cache of full tool-result snapshots behind opaque
        # handles. The read-only `result_read` tool pages them WITHOUT
        # re-running the producing tool (slow bash/webfetch/grep especially).
        # Memory-only and cleared when the context is reclaimed / run resets,
        # so a resumed agent never serves a stale snapshot.
        self.result_store = ResultStore()
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
        # Role-filtered skill triggers (name + description), rendered by the
        # runtime at delegate time and folded into the static system-prompt
        # block. Empty when the library has no skills (or none for this role).
        self._skill_triggers: str = ""
        # Set once this agent's heavyweight in-memory context has been reclaimed
        # by ``collect_garbage()``. Guards repeated collection and lets a parent
        # know its child is already just a lightweight outcome stub.
        self._context_freed: bool = False
        # Final live-context message count, captured when the context is
        # reclaimed so overviews can still show what a completed agent was
        # working with instead of dropping to 0.
        self._final_context_messages: int | None = None

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
    def live_context_messages(self) -> int:
        """Live context message count for overviews.

        Reports ``len(context.messages)`` while the agent holds its context,
        and the retained final count once ``collect_garbage()`` has reclaimed
        it — so a completed agent keeps its message figure instead of 0.
        """
        if self._context_freed:
            return self._final_context_messages or 0
        return len(self.context.messages)

    @property
    def iteration_count(self) -> int:
        """Number of LLM iterations this agent has executed."""
        return self._iteration

    def usage_summary(self) -> dict[str, Any]:
        """Live cumulative usage + context state for this agent.

        Cache-clean feedback: the agent reads its own counters via the
        ``usage`` tool rather than the runtime appending a changing per-turn
        observation message (which would zero the provider prompt cache).
        Public method so callers (e.g. ``ToolContext``) never reach into
        ``_runtime`` / ``_iteration`` directly — the narrow-seam contract.
        """
        u = self._runtime.get_usage(self.id)
        return {
            "agent_id": self.id,
            "iteration": self._iteration,
            "messages_in_context": self.message_count,
            "cumulative_messages_sent": u.get("message_count", 0),
            "cumulative_prompt_tokens": u.get("prompt_tokens", 0),
            "cumulative_completion_tokens": u.get("completion_tokens", 0),
            "cumulative_total_tokens": u.get("total_tokens", 0),
            "cumulative_cached_tokens": u.get("cached_tokens", 0),
            "live_context_token_estimate": self.context.estimate_prompt_tokens(),
            "max_agent_tokens": self.max_agent_tokens,
        }

    def is_rot(self) -> bool:
        """True when the agent stopped because its *context* is the problem.

        Poisoned/shallow-rot indicators: repeated identical tool calls, a safety
        limit (max iterations / timeout), or so many iterations that the context
        has grown unbounded. Self-heal uses this to prefer a fresh worker over
        resuming a poisoned context.
        """
        return (
            self._repeated_calls_detected
            or (self._terminated_by_safety and not self._timed_out)
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
        self._final_context_messages = len(self.context.messages)
        self._context_freed = True

        self.context.messages = []
        self.context.turns = {}
        self.context.turn_order = []
        self.context.pruned = set()
        self.context.prune_markers = {}
        # Reset turn accounting so a resumed context rebuilds cleanly.
        self.context.turn_counter = 0
        # The loop-guard deques are only meaningful mid-run; drop their contents.
        self._loop_guard.clear()
        self.result_store.clear()
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

    # -- loop-guard compatibility shims ----------------------------------
    # Detection state and tunables used to be plain attributes on the Agent;
    # they now live inside the composable LoopGuard policy. Tests and callers
    # still read/write the old private names, so expose them as forwarding
    # properties.

    @property
    def repeated_call_limit(self) -> int:
        return self._loop_guard.repeated_call_limit

    @repeated_call_limit.setter
    def repeated_call_limit(self, value: int) -> None:
        self._loop_guard.repeated_call_limit = max(int(value), 1)

    @property
    def _repeated_recovery_left(self) -> int:
        return self._loop_guard.repeated_recovery_left

    @_repeated_recovery_left.setter
    def _repeated_recovery_left(self, value: int) -> None:
        self._loop_guard.repeated_recovery_left = max(int(value), 0)

    @property
    def _repeated_call_exempt_tools(self) -> tuple[str, ...]:
        return self._loop_guard.exempt_tools

    @_repeated_call_exempt_tools.setter
    def _repeated_call_exempt_tools(self, value: Any) -> None:
        self._loop_guard.exempt_tools = tuple(value)

    @property
    def _repeated_calls_detected(self) -> bool:
        return self._loop_guard.repeated_calls_detected

    @_repeated_calls_detected.setter
    def _repeated_calls_detected(self, value: bool) -> None:
        self._loop_guard.repeated_calls_detected = bool(value)

    @property
    def _near_identical_threshold(self) -> int:
        return self._loop_guard.near_identical_threshold

    @_near_identical_threshold.setter
    def _near_identical_threshold(self, value: int) -> None:
        self._loop_guard.near_identical_threshold = max(int(value), 1)

    @property
    def _near_identical_window(self) -> int:
        return self._loop_guard.near_identical_window

    @_near_identical_window.setter
    def _near_identical_window(self, value: int) -> None:
        self._loop_guard.near_identical_window = max(int(value), 2)

    @property
    def _near_identical_similarity(self) -> float:
        return self._loop_guard.near_identical_similarity

    @_near_identical_similarity.setter
    def _near_identical_similarity(self, value: float) -> None:
        self._loop_guard.near_identical_similarity = float(value)

    @property
    def _near_identical_tools(self) -> tuple[str, ...]:
        return self._loop_guard.near_identical_tools

    @_near_identical_tools.setter
    def _near_identical_tools(self, value: Any) -> None:
        self._loop_guard.near_identical_tools = tuple(value)

    @property
    def _near_identical_warning_attempts(self) -> int:
        return self._loop_guard.near_identical_warning_attempts

    @_near_identical_warning_attempts.setter
    def _near_identical_warning_attempts(self, value: int) -> None:
        self._loop_guard.near_identical_warning_attempts = max(int(value), 0)

    @property
    def _near_identical_warned(self) -> dict[str, int]:
        return self._loop_guard.near_identical_warned

    @_near_identical_warned.setter
    def _near_identical_warned(self, value: Any) -> None:
        self._loop_guard.near_identical_warned = dict(value)

    @property
    def _recent_batches(self) -> Any:
        return self._loop_guard.recent_batches

    @_recent_batches.setter
    def _recent_batches(self, value: Any) -> None:
        self._loop_guard.recent_batches = value

    @property
    def _recent_tool_signatures(self) -> Any:
        return self._loop_guard.recent_tool_signatures

    @_recent_tool_signatures.setter
    def _recent_tool_signatures(self, value: Any) -> None:
        self._loop_guard.recent_tool_signatures = value

    @property
    def _recent_messages(self) -> Any:
        return self._loop_guard.recent_messages

    @_recent_messages.setter
    def _recent_messages(self, value: Any) -> None:
        self._loop_guard.recent_messages = value

    @property
    def _recent_delegate_targets(self) -> Any:
        return self._loop_guard.recent_delegate_targets

    @_recent_delegate_targets.setter
    def _recent_delegate_targets(self, value: Any) -> None:
        self._loop_guard.recent_delegate_targets = value

    @property
    def _recent_near_identical(self) -> Any:
        return self._loop_guard.recent_near_identical

    @_recent_near_identical.setter
    def _recent_near_identical(self, value: Any) -> None:
        self._loop_guard.recent_near_identical = value

    # -- nudge / spawn-warning compatibility shims -----------------------
    # The nudge thresholds / attempt budgets used to be plain attributes on the
    # Agent; they now live inside the stateful reactive policies (NudgePolicy /
    # SpawnWarningPolicy). Tests and callers still read/write the old private
    # names, so expose them as forwarding properties.

    @property
    def _delegate_nudge_threshold(self) -> int:
        return self._nudge_policy.delegate_nudge_threshold

    @_delegate_nudge_threshold.setter
    def _delegate_nudge_threshold(self, value: int) -> None:
        self._nudge_policy.delegate_nudge_threshold = max(int(value), 1)

    @property
    def _delegate_nudge_attempts(self) -> int:
        return self._nudge_policy.delegate_nudge_attempts

    @_delegate_nudge_attempts.setter
    def _delegate_nudge_attempts(self, value: int) -> None:
        self._nudge_policy.delegate_nudge_attempts = max(int(value), 0)

    @property
    def _delegate_nudge_left(self) -> int:
        return self._nudge_policy.delegate_nudge_left

    @_delegate_nudge_left.setter
    def _delegate_nudge_left(self, value: int) -> None:
        self._nudge_policy.delegate_nudge_left = max(int(value), 0)

    @property
    def _iteration_warning_margin(self) -> int:
        return self._nudge_policy.iteration_warning_margin

    @_iteration_warning_margin.setter
    def _iteration_warning_margin(self, value: int) -> None:
        self._nudge_policy.iteration_warning_margin = max(int(value), 1)

    @property
    def _iteration_warning_attempts(self) -> int:
        return self._nudge_policy.iteration_warning_attempts

    @_iteration_warning_attempts.setter
    def _iteration_warning_attempts(self, value: int) -> None:
        self._nudge_policy.iteration_warning_attempts = max(int(value), 0)

    @property
    def _iteration_warning_left(self) -> int:
        return self._nudge_policy.iteration_warning_left

    @_iteration_warning_left.setter
    def _iteration_warning_left(self, value: int) -> None:
        self._nudge_policy.iteration_warning_left = max(int(value), 0)

    @property
    def _spawn_warning_left(self) -> int:
        return self._spawn_warning_policy.warning_left

    @_spawn_warning_left.setter
    def _spawn_warning_left(self, value: int) -> None:
        self._spawn_warning_policy.warning_left = max(int(value), 0)

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

    def checkpoint(self, note: str, *, done: list[str] | None = None) -> str:
        """Persist current state with a milestone note, enabling crash-resume.

        ``done`` (optional) lists plan steps that were just completed; they are
        advanced in the focus ledger so the persisted plan reflects real
        progress (rather than re-stating every step as pending on resume).
        """
        if done:
            for item in done:
                self.mark_focus_done(str(item))
        self._checkpoint_notes.append(note)
        self.persist_checkpoint()
        prefix = f" ({len(done)} step(s) marked done)" if done else ""
        return f"Checkpoint recorded (state on disk){prefix} — note: {note[:80]}"

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

    def set_skill_triggers(self, triggers: str) -> None:
        """Inject the role-filtered skill trigger block into the static steerage.

        Rendered by the runtime at delegate time (empty when no skills apply to
        this agent's role). Lives in the static system-prompt block so the
        prompt prefix stays byte-identical for provider caching.
        """
        self._skill_triggers = triggers

    @property
    def environment_info(self) -> str:
        return self._environment_render

    @property
    def skill_triggers(self) -> str:
        """The role-filtered skill trigger block in this agent's steerage."""
        return self._skill_triggers

    @property
    def skills(self) -> Any:
        """The runtime's discovered skill registry (or None when no runtime)."""
        if self._runtime is None:
            return None
        return self._runtime.skills

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
        self._loop_guard.clear()
        self.result_store.clear()
        self._has_delegated = False
        self._nudge_policy.reset()
        self._brief_policy.reset()
        # A fresh run is a fresh wall-clock budget: clear any prior safety-stop
        # markers so a resumed/re-run agent that finishes cleanly is not still
        # tagged timed-out / safety-stopped.
        self._terminated_by_safety = False
        self._timed_out = False
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
            # Fresh-turn budget: reset the per-run loop-guard state that run()
            # initialises, so iterations / wall-clock / warning counters do not
            # accumulate across interactive REPL turns (a long session would
            # otherwise trip the safety caps prematurely). The conversation
            # (context) and result-store handles are deliberately retained.
            self._iteration = 0
            self._loop_guard.clear()
            self._started_at = time.monotonic()
            self._has_delegated = False
            self._nudge_policy.reset()
            self._brief_policy.reset()
            self._terminated_by_safety = False
            self._timed_out = False
            self.context.messages.append({"role": "user", "content": user_message})
            await self._run_guarded()

    async def _llm_call_with_retry(
        self, tools: list[dict], messages: list[dict[str, Any]] | None = None
    ) -> Any:
        llm = self.llm
        assert llm is not None
        msgs = messages if messages is not None else self.context.messages
        # Session-pinned config: keep every request of this conversation on the
        # same provider/cache via the agent's stable session_id. A rate-limited
        # call may drop this pin on retry (fallback_on_rate_limit) so the
        # provider can route the retry elsewhere.
        cfg = LLMConfig(model=llm.default_model, session_id=self.session_id)
        # Retry/backoff decisions live in the host-agnostic RetryPolicy; the
        # agent's scalar knobs (overridable via config / tests) feed it. The
        # loop below drives the I/O; the policy decides.
        policy = RetryPolicy(
            retry_max_attempts=self.retry_max_attempts,
            rate_limit_max_attempts=self.rate_limit_max_attempts,
            retry_base_delay_seconds=self.retry_base_delay_seconds,
            retry_max_delay_seconds=self.retry_max_delay_seconds,
            retry_jitter_seconds=self.retry_jitter_seconds,
            rate_limit_backoff_multiplier=self.rate_limit_backoff_multiplier,
            fallback_on_rate_limit=self.fallback_on_rate_limit,
        )

        # Attempt budgets by failure class. A rate limit is NOT the same as a
        # generic transient error: shared upstream pool overloads (DeepInfra
        # `engine_overloaded`) routinely outlast the seconds of backoff a plain
        # timeout budget allows. Counting per class means one kind of failure
        # never consumes the other kind's patience.
        budgets = policy.budgets
        attempts: dict[bool, int] = {False: 0, True: 0}
        worst_budget = policy.worst_budget
        last_error: Exception | None = None

        for attempt in range(worst_budget):
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
                rate_limited = policy.is_rate_limit(e)
                attempts[rate_limited] += 1
                if not policy.is_retryable(e) or attempts[rate_limited] >= budgets[rate_limited]:
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
                            policy.per_call_timeout_message(self._call_timeout_seconds)
                        ) from e
                    raise
                self._runtime.record_retry(self.id)
                # Adaptive backoff: exponential in the retry count for this
                # failure class, scaled up for rate limits, honoring a provider
                # Retry-After header, and always capped at the configured ceiling.
                retry_count = attempts[rate_limited]
                delay = policy.delay_seconds(
                    rate_limited=rate_limited,
                    retry_count=retry_count,
                    retry_after=policy.retry_after_seconds(e),
                )
                await asyncio.sleep(delay + random.uniform(0, self.retry_jitter_seconds))
                if policy.should_drop_session_pin(
                    rate_limited=rate_limited, has_session_id=bool(cfg.session_id)
                ):
                    # Drop the session pin: retry outside the pinned provider so
                    # OpenRouter can route to one that is not overloaded. Only
                    # this retry is affected; the next turn re-pins via
                    # `self.session_id`.
                    cfg = LLMConfig(model=llm.default_model)
        if last_error is not None:
            raise last_error

    @staticmethod
    def _is_rate_limit(exc: Exception) -> bool:
        """True for HTTP 429 / explicit rate-limit failures (see ``RetryPolicy``)."""
        return RetryPolicy.is_rate_limit(exc)

    @staticmethod
    def _retry_after_seconds(exc: Exception) -> float | None:
        """Seconds to wait before retrying, from a provider Retry-After header
        (see ``RetryPolicy.retry_after_seconds``)."""
        return RetryPolicy.retry_after_seconds(exc)

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        """True for transient failures (see ``RetryPolicy.is_retryable``)."""
        return RetryPolicy.is_retryable(exc)

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
            timeout = TimeoutPolicy(timeout_seconds=self._safety_timeout_seconds)
            remaining = timeout.remaining_seconds(time.monotonic() - self._started_at)
            if remaining <= 0:
                self._terminated_by_safety = True
                self._timed_out = True
                self.fail(
                    timeout.timeout_message(
                        self._safety_timeout_seconds, self._iteration
                    )
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
            self._timed_out = True
            self.fail(
                TimeoutPolicy(timeout_seconds=self._safety_timeout_seconds).timeout_message(
                    self._safety_timeout_seconds or 0.0, self._iteration, mid_call=True
                )
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

        limits = self._runtime.agent_policy.limits_line(
            max_agent_tokens=child.max_agent_tokens,
            timeout=child._safety_timeout_seconds,
        )
        if limits:
            result["limits"] = limits

        if child.last_failure:
            failure = child.last_failure.error[:500]
            if getattr(child, "_timed_out", False):
                failure += "\n\n" + self._timeout_resume_guidance(child.id)
            result["failure"] = failure

        return json.dumps(result, indent=2)

    @staticmethod
    def _timeout_resume_guidance(agent_id: str) -> str:
        """Parent-facing directions for continuing a child that ran out of wall clock.

        A timeout never self-heals, so the failure surfaced to the parent says
        WHAT happened and HOW to retry it (resume the same context vs a clean
        retry vs re-delegate)."""
        return (
            "[timeout] This child hit its wall-clock budget and was NOT "
            "auto-retried so you can decide what to do with it. Its context is "
            f"intact (a timeout is not rot), so you may:\n"
            f"  - resume(agent_id=\"{agent_id}\", strategy=\"resume\") to continue "
            "the SAME context and finish the remaining work,\n"
            f"  - resume(agent_id=\"{agent_id}\", strategy=\"fresh\") to retry "
            "the task from a clean slate,\n"
            f"  - or re-delegate this unit of work to a fresh child.\n"
            "Only direct children you delegated can be resumed."
        )

    async def _fold_child_result(self, child: Agent) -> tuple[str, Agent]:
        """Format a settled child for injection into the parent's context,
        self-healing it first if it finished without a deliverable.

        Returns ``(formatted, child)`` where ``child`` is the (possibly
        replaced) agent the caller should garbage-collect. Shared by the
        streaming harvest and the interrupted deferred-gather fold-back so
        both paths lose no child result.
        """
        if not self._runtime._has_deliverable(child):
            child = await self._runtime._recover(child)
        return self._format_delegate_result(child), child

    # -- run loop ---------------------------------------------------------

    def _safety_check(self) -> bool:
        """Return True when a safety limit was hit and the loop must stop."""
        timeout = TimeoutPolicy(timeout_seconds=self._safety_timeout_seconds)
        if (
            timeout.enabled
            and self._started_at is not None
            and timeout.exceeded(time.monotonic() - self._started_at)
        ):
            self._terminated_by_safety = True
            self._timed_out = True
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
                timeout.timeout_message(
                    self._safety_timeout_seconds, self._iteration
                )
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
            token_policy = TokenBudgetPolicy(max_agent_tokens=self.max_agent_tokens)
            if token_policy.exceeded(current):
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
                self.fail(token_policy.exceed_message(current))
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

        The mission-command brief (the parent's intent) also lives here, for
        the same reason plus one more: ``context.compress`` keeps only the
        system message, so the parent's intent — the child's decision
        criterion — must not live in a prunable/compressible user message.
        """
        blocks: list[str] = []
        brief = build_brief_block(
            intent=self.task.intent,
            end_state=self.task.end_state,
            constraints=self.task.constraints,
            authority=self.task.authority,
        )
        if brief:
            blocks.append(f"Mission brief from your parent:\n{brief}")
        focus_text = render_focus(self._focus, iteration=1)
        if focus_text:
            blocks.append(focus_text)
        budget_policy = TokenBudgetPolicy(max_agent_tokens=self.max_agent_tokens)
        guidance = budget_policy.budget_guidance()
        if guidance:
            blocks.append(guidance)
        timeout_guidance = budget_policy.timeout_guidance(self._safety_timeout_seconds)
        if timeout_guidance:
            blocks.append(timeout_guidance)
        if self.environment_info:
            blocks.append(self.environment_info)
        if self._skill_triggers:
            blocks.append(self._skill_triggers)
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
            # Only open a fresh deferred batch when there is no carryover from
            # an interrupted wait: children left over from a mid-run input keep
            # their place so this turn's gather folds them as well instead of
            # dropping the earlier delegation.
            if not self.stream_children and self._deferred_delegates is None:
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
            self._telemetry.tool_finished(tc, content, result_id=getattr(result, "result_id", None))
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
        # The loop-safety check used to run here; it is now applied by the
        # post-turn reactive pass (_run_reactive_pass) so ALL metric-reactive
        # policies — LoopGuard included — ride the shared directive path.
        return False

    @staticmethod
    def _delegate_target_signature(arguments: dict[str, Any]) -> str:
        """Normalized key for a delegate call, keyed on the referenced path(s).

        Catches the failure mode where an orchestrator re-reads *the same file*
        (or re-explores *the same directory*) by spinning a fresh sub-agent each
        time with superficially different wording (e.g. 'read X verbatim' →
        'read X from offset N' → ...). Delegates to the shared
        ``delegate_target_signature`` (also used by the runtime's same-target
        spawn cap) so both in-context loop detection and the lineage-wide cap
        agree on the signature.
        """
        description = str(arguments.get("description", ""))
        return delegate_target_signature(description)

    @staticmethod
    def _normalize_tool_signature(name: str, arguments: dict[str, Any]) -> str:
        """Canonical, whitespace-insensitive key for a single tool call.

        See ``core/policies/loop_guard.py`` for the reference implementation.
        """
        return normalize_tool_signature(name, arguments)

    @staticmethod
    def _paginationless_signature(
        name: str, arguments: dict[str, Any], exclude: set[str] | None = None
    ) -> str:
        """Signature used for *similarity* scoring: pagination knobs are dropped.

        See ``core/policies/loop_guard.py`` for the reference implementation.
        """
        return paginationless_signature(name, arguments, exclude=exclude)

    def _similarity(self, a: str, b: str) -> float:
        return similarity(a, b)

    @staticmethod
    def _bash_family(command: str) -> str:
        """Pagination-insensitive family key for a bash command.

        See ``core/policies/loop_guard.py`` for the reference implementation.
        """
        return bash_family(command)

    @staticmethod
    def _bash_read_regions(command: str) -> list[tuple[str, int, int]]:
        """Extract (file, lo, hi) reads from a bash command.

        See ``core/policies/loop_guard.py`` for the reference implementation.
        """
        return bash_read_regions(command)

    @staticmethod
    def _regions_overlap(a: list[tuple[str, int, int]], b: list[tuple[str, int, int]]) -> bool:
        """True when the same file is read at overlapping ranges in both sets."""
        return regions_overlap(a, b)

    def add_reactive_policy(self, policy: ReactivePolicy) -> None:
        """Register a metric-reactive policy on this agent.

        The plugin seam: a host-registered policy only implements ``name`` +
        ``evaluate(observation)``; its directives flow through the same applier
        as the built-in nudges / loop guard.
        """
        self.reactive_policies.add(policy)

    def _observe(self, response: Any | None = None) -> Observation:
        """Snapshot of the live metrics handed to the reactive policies."""
        return Observation(
            iteration=self._iteration,
            max_iterations=self._safety_max_iterations,
            has_delegated=self._has_delegated,
            tool_calls=list(response.tool_calls) if response is not None else [],
            assistant_content=(response.content if response is not None else None),
            tree_depth=self._depth,
            spawn_usage=self._runtime.spawn_usage(self) if self._runtime is not None else None,
            agent_id=self.id,
            task_description=self.task.description,
            role=self.task.role,
        )

    def _apply_prompt_injection(self, injection: PromptInjection) -> bool:
        """Apply one directive from a reactive policy: emit the activity event,
        append its message to the live context, and — for a critical directive —
        fail the run. Returns True when the run must stop."""
        self._event_bus.emit_activity(ActivityEvent(
            agent_id=self.id,
            event_type=ActivityEventType.SAFETY_WARNING,
            data={"warning_type": injection.warning_type, **(injection.data or {})},
        ))
        if injection.message:
            self.context.append({"role": "user", "content": injection.message})
        if injection.stop:
            self.fail(injection.message or injection.warning_type)
            return True
        return False

    def _run_reactive_pass(self, response: Any) -> bool:
        """One post-turn pass over the registered reactive policies.

        Builds the observation once, lets each policy (in registration order)
        decide, and applies the returned directives via the shared applier.
        Returns True when a critical directive stopped the run.
        """
        observation = self._observe(response)
        stop = False
        for injection in self.reactive_policies.evaluate_all(observation):
            if self._apply_prompt_injection(injection):
                stop = True
                break
        return stop

    def _check_repeated_calls(self, response: Any) -> bool:
        """Return True when repeated calls were detected (loop stops).

        Back-compat entry point for the ``LoopGuard`` reactive policy. The run
        loop calls the same policy at commit time (so loop detection also fires
        before a stream-harvest ``continue``); this standalone entry lets tests
        and hosts drive just the loop policy through the shared directive path.
        """
        stop = False
        for injection in self._loop_guard.evaluate(self._observe(response)):
            if self._apply_prompt_injection(injection):
                stop = True
        return stop

    def _apply_loop_action(self, action: LoopAction) -> bool:
        """Apply one ``LoopAction`` verdict. Returns True when the run must
        stop (the recovery ladder force-failed the agent). Back-compat wrapper
        over the shared directive applier."""
        return self._apply_prompt_injection(loop_action_to_injection(action))

    def _maybe_nudge_delegation(self) -> None:
        """Emit a stable, one-off reminder when an agent never delegates.

        Scoped to agents that have reached ``delegate_nudge_threshold`` turns
        without any ``delegate`` call. Fires at most ``delegate_nudge_attempts``
        times and appends a fixed-text user message at the end of the context —
        never mutating a prior message — so the prompt prefix (and the
        provider's cache contiguity) is preserved after the nudge lands. The
        condition + wording live in the host-agnostic ``NudgePolicy``.
        """
        decision = self._nudge_policy.delegate_nudge(
            iteration=self._iteration,
            attempts_left=self._nudge_policy.delegate_nudge_left,
            has_delegated=self._has_delegated,
        )
        if not decision.fire:
            return
        self._nudge_policy.delegate_nudge_left -= 1
        self._apply_prompt_injection(
            PromptInjection.warning(
                decision.note or "",
                warning_type=decision.warning_type,
                data=decision.data,
            )
        )

    def _maybe_warn_iterations_low(self) -> None:
        """Inject ONE hard wrap-up message when iterations are running low.

        When remaining iterations (``safety_max_iterations - iteration``) drop
        to ``iteration_warning_margin`` or fewer, append a fixed, assertive
        notice telling the agent to stop expanding scope, finish off what it
        can, and hand the unfinished remainder plus any relevant context to its
        parent so it can decide what to schedule in other tasks. Fires at most
        ``iteration_warning_attempts`` times; tail-append-only so the prompt
        prefix (and the provider's cache contiguity) is preserved. The
        condition + wording live in the ``NudgePolicy``.
        """
        decision = self._nudge_policy.iteration_warning(
            iteration=self._iteration,
            attempts_left=self._nudge_policy.iteration_warning_left,
        )
        if not decision.fire:
            return
        self._nudge_policy.iteration_warning_left -= 1
        self._apply_prompt_injection(
            PromptInjection.warning(
                decision.note or "",
                warning_type=decision.warning_type,
                data=decision.data,
            )
        )

    def _maybe_warn_spawn_limits(self) -> None:
        """Inject ONE non-fatal notice when a delegation cap is nearly exhausted.

        Tail-append-only, fires at most the agent's spawn-warning budget times
        total, and never fails the run. The notice lists which cap is near its
        limit and tells the agent to consolidate (finish in-context / verify
        existing children / escalate) before the hard refusal kicks in.
        """
        for injection in self._spawn_warning_policy.evaluate(self._observe()):
            self._apply_prompt_injection(injection)

    def submit_input(self, message: str) -> None:
        """Queue a mid-run user message for this agent.

        A working agent finishes its current turn before the message lands as a
        fresh user turn; if the agent is instead blocked waiting on its children
        (deferred or streaming gather), the injection interrupts that wait so it
        reacts immediately. Interrupted children are preserved: they are
        re-gathered and their results fold into the parent's context once they
        settle, so the mid-run answer never loses the in-flight delegation."""
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
                # Loop detection runs at commit time — BEFORE a stream-harvest
                # `continue` — so a parent that keeps delegating while its
                # children settle is still bounded by the same detection a
                # blocking gather would apply.
                if self._check_repeated_calls(response):
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
            # Post-turn reactive pass: every registered metric-reactive policy
            # (the built-in nudges + spawn near-cap warning, plus any host-
            # registered policies) observes THIS turn and may inject a
            # directive into the context. A critical directive stops the run.
            if self._run_reactive_pass(response):
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

        # Race the full child-gather against mid-run user input so a parent
        # blocked on its children reacts to injected input immediately. On
        # interruption the children are NOT dropped: still-running ones stay
        # registered so the run loop re-gathers them next turn and folds their
        # results into context then, and any child that settled in the same
        # instant is folded here and now.
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
            # User input interrupted the wait. Children that settled in the same
            # instant are folded into context; still-running children keep their
            # place in ``_deferred_delegates`` so the next turn re-gathers them.
            # The run loop drains the queued input as a fresh user message
            # (always *after* the current turn is committed, so message ordering
            # stays valid).
            leftovers: list[tuple[str, Agent, asyncio.Task[None]]] = []
            for tcid, child, task in pending:
                if task.done():
                    folded, final = await self._fold_child_result(child)
                    self.context.append({
                        "role": "user",
                        "content": f"[child settled]\n{folded}",
                    })
                    final.collect_garbage()
                else:
                    leftovers.append((tcid, child, task))
            if leftovers:
                self._deferred_delegates = leftovers
            return

        # FIRST_COMPLETED fired: at least one child settled, but stragglers may
        # still be running. Never block finalization on them — await only the
        # tasks that are already done and detach the rest (they keep their place
        # in ``_deferred_delegates`` so the next turn re-gathers them), instead
        # of awaiting every pending task unconditionally.
        deferred_map: dict[str, Agent] = {}
        leftovers: list[tuple[str, Agent, asyncio.Task[None]]] = []
        for tcid, child, task in pending:
            if not task.done():
                leftovers.append((tcid, child, task))
                continue
            outcome = task.result()
            deferred_map[tcid] = child
            if isinstance(outcome, BaseException) and not isinstance(outcome, asyncio.CancelledError):
                if not child.last_report and not child.last_failure:
                    child.fail(f"Child agent raised: {outcome}")
        if leftovers:
            self._deferred_delegates = leftovers

        for tcid, child in list(deferred_map.items()):
            if not self._runtime._has_deliverable(child):
                deferred_map[tcid] = await self._runtime._recover(child)

        patched: set[str] = set()
        for r in results:
            tcid = r["tool_call_id"]
            if tcid in deferred_map:
                r["content"] = self._format_delegate_result(deferred_map[tcid])
                patched.add(tcid)

        # Children left over from an interrupted earlier gather have tool-call
        # ids that are not part of this turn's results; fold them streaming-style
        # so a mid-run answer never loses the pre-interruption delegation.
        for tcid, child in list(deferred_map.items()):
            if tcid not in patched:
                self.context.append({
                    "role": "user",
                    "content": f"[child settled]\n{self._format_delegate_result(child)}",
                })

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
            folded, final = await self._fold_child_result(child)
            self.context.append({
                "role": "user",
                "content": f"[child settled]\n{folded}",
            })
            final.collect_garbage()
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
        intent: str | None = None,
        end_state: str | None = None,
        constraints: Sequence[str] | None = None,
        authority: str | None = None,
        **metadata: Any,
    ) -> Agent:
        child_task = Task(
            description=description,
            role=role,
            system_prompt=system_prompt,
            parent_id=self.task.id,
            intent=intent,
            end_state=end_state,
            constraints=list(constraints) if constraints else [],
            authority=authority,
            metadata=metadata,
        )
        child = self._runtime.delegate(child_task, parent=self, agent_type=agent_type)
        self.children.append(child)
        return child

    def emit_activity(self, event: ActivityEvent) -> None:
        self._event_bus.emit_activity(event)

    def get_other_agent(self, agent_id: str) -> Agent | None:
        return self._runtime.get_agent(agent_id)

    @property
    def comms(self):
        """The runtime's communication backend, or None when the layer is off."""
        return self._runtime.comms if self._runtime is not None else None

    def comms_ref(self):
        """Minimal sender identity handed to the comms routing backends."""
        from .comms import AgentRef

        return AgentRef(
            agent_id=self.id,
            parent_id=self.parent.id if self.parent is not None else None,
            role=self.task.role,
        )

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
        if not ToolPermissionPolicy.killable(target.task.status):
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
    def reference_root(self) -> Any:
        return self._reference_root

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
            "timed_out": self._timed_out,
            "limits": self._runtime.agent_policy.limits_line(
                max_agent_tokens=self.max_agent_tokens,
                timeout=self._safety_timeout_seconds,
            ),
            "heal": {
                "diagnosis": self._runtime.heal_diagnosis(self),
                "resumes": self._runtime.get_heal_count(self.id, "resume"),
                "fresh": self._runtime.get_heal_count(self.id, "fresh"),
                # True when the runtime would re-run its automatic self-heal
                # over this agent right now (failed, or no on-disk deliverable).
                # A timed-out agent is exempt: it is never auto-healed, so the
                # parent decides via the resume tool.
                "recoverable": (
                    not self._killed
                    and not self._timed_out
                    and self.task.status is not TaskStatus.escalated
                    and not (
                        self.last_report is not None
                        and self._runtime._has_deliverable(self)
                    )
                ),
                "resume_hint": self._timeout_resume_guidance(self.id) if self._timed_out else None,
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

    def _delegate_budget_line(self) -> str:
        """Compact delegation-cap status appended to every delegate() result.

        Lets the model self-regulate BEFORE a refusal: it sees how many agents
        have been spawned (vs ``safety.max_agents``), its tree depth (vs
        ``safety.max_depth``), and the most re-delegated target along its lineage
        (vs ``safety.max_same_target_delegations``). Cf. the non-fatal
        ``_maybe_warn_spawn_limits`` notice that fires at ~80% of a cap.
        """
        try:
            usage = self._runtime.spawn_usage(self)
        except Exception:
            return ""
        return self._runtime.spawn_policy.budget_line(usage)

    async def run_delegate_tool(
        self,
        description: str,
        *,
        role: str | None = None,
        system_prompt: str | None = None,
        agent_type: str | None = None,
        intent: str | None = None,
        end_state: str | None = None,
        constraints: Sequence[str] | None = None,
        authority: str | None = None,
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
        try:
            child = self.delegate(
                description, agent_type=agent_type, role=role, system_prompt=system_prompt,
                intent=intent, end_state=end_state,
                constraints=constraints, authority=authority,
            )
        except DelegationLimit as exc:
            # A spawn cap refused the delegation: no agent was created. Surface
            # the refusal + remaining budget to the model so it finishes
            # in-context / verifies what it has / escalates, instead of retrying
            # the same refused spawn forever.
            self._event_bus.emit_activity(ActivityEvent(
                agent_id=self.id,
                event_type=ActivityEventType.SAFETY_WARNING,
                data={
                    "warning_type": "delegation_refused",
                    "reason": exc.reason,
                    "usage": self._runtime.spawn_usage(self),
                },
            ))
            return json.dumps({
                "child_id": None,
                "status": "refused",
                "error": exc.reason,
                "suggestion": (
                    "No sub-agent was created. Either solve this unit of work "
                    "in-context with your own tools, read/verify children you "
                    "already delegated, return the remaining work to your parent, "
                    "or escalate — but do NOT call delegate() with the same "
                    "target again."
                ),
                "budget": self._delegate_budget_line(),
            }, indent=2)
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
            return json.dumps({
                "child_id": child.id,
                "status": "running",
                "budget": self._delegate_budget_line(),
            }, indent=2)
        if self._deferred_delegates is not None:
            self._deferred_delegates.append((tool_call_id, child, task))
            return json.dumps({
                "child_id": child.id,
                "status": "pending",
                "budget": self._delegate_budget_line(),
            }, indent=2)
        await task
        if not self._runtime._has_deliverable(child):
            child = await self._runtime._recover(child)
        result = json.loads(self._format_delegate_result(child))
        result["budget"] = self._delegate_budget_line()
        child.collect_garbage()
        return json.dumps(result, indent=2)

    def report(self, payload: ReportPayload) -> None:
        if self.stream_children:
            self._cancel_stream_children()
        self.outcome.report = payload
        self._runtime.deliver_report(self.id, payload)

    def record_archived_artifact(self, artifact_id: str) -> None:
        """Track an artifact archived mid-run (via the ``archive`` tool).

        These ids are linked into the final report commit so temp/working
        artifacts show up in repository provenance, not just the artifact
        index. The public method keeps tool-facing callers off the private
        ``_archived_artifact_ids`` list (narrow ToolContext seam).
        """
        self._archived_artifact_ids.append(artifact_id)

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

        strategy, strategy_error = ResumePlanner.validate(strategy)
        if strategy_error:
            return json.dumps({
                "error": strategy_error,
            })
        assert strategy is not None

        failures: list[str] = []
        effective: Agent = target
        diagnosis = self._runtime._diagnose(target)
        counts = self._runtime._heal_counts_for(target.id)
        note_text = note.strip() if note else ""

        rot_refusal = ResumePlanner.refusal_for_rot(strategy, diagnosis)
        if rot_refusal is not None:
            return json.dumps({
                "agent_id": agent_id,
                "status": "refused_rot",
                "diagnosis": diagnosis,
                "error": rot_refusal,
            })

        def _resume_nudge(child: Agent) -> str:
            reason = (
                child.last_failure.error[:600]
                if child.last_failure
                else "the previous attempt did not produce an on-disk deliverable"
            )
            base = (
                f"A previous attempt of this task failed with: {reason}. "
                f"Resume your current work from your documented progress below — "
                f"your prior context (plan, steps, partial results) is intact. "
                f"Continue from where you left off; correct the failure; do not "
                f"repeat the same mistake — then write your deliverable(s) to "
                f"disk and finish with report()."
            )
            progress = progress_summary_block(
                objective=child._focus.objective,
                deliverable=child._focus.deliverable,
                acceptance=list(child._focus.acceptance),
                pending=list(child._focus.pending),
                done=list(child._focus.done),
                checkpoint_notes=list(child._checkpoint_notes),
            )
            return f"{base}\n\n{progress}\n\nParent instruction: {note_text}" if note_text else f"{base}\n\n{progress}"

        healed = False
        # Layer 1: resume the same child on a blunt miss (planning above; this
        # branch only executes + budgets).
        if ResumePlanner.should_attempt_resume(strategy, diagnosis):
            if counts["resume"] < self._runtime.heal_policy.max_resumes:
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
                    ResumePlanner.budget_exhausted(
                        "resume", counts["resume"],
                        self._runtime.heal_policy.max_resumes,
                    )
                )

        # Layer 2: fresh worker when resuming didn't heal (or rot / forced).
        if ResumePlanner.should_attempt_fresh(strategy, healed=healed):
            if counts["fresh"] < self._runtime.heal_policy.max_fresh:
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
                if fresh is None:
                    failures.append(
                        "fresh worker refused: a delegation cap "
                        "(max_agents / max_depth / max_same_target_delegations) "
                        "was reached — no new agent was spawned"
                    )
                else:
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
                    ResumePlanner.budget_exhausted(
                        "fresh", counts["fresh"],
                        self._runtime.heal_policy.max_fresh,
                    )
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
