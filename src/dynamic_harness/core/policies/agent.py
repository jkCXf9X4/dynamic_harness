"""Agent construction policy as a composable policy bundle.

``Runtime.delegate()`` used to thread ~18 config-derived knobs into every
agent — 12 as constructor kwargs (the two base/custom-class branches written
verbatim) and 6 as post-construction attribute patches. That chain is now a
single ``AgentPolicy`` object: the runtime constructs one bundle from config
in ``__init__`` (with config as the ONLY default source) and ``delegate()``
dereferences it. The policy is host-agnostic — it imports neither an agent nor
a runtime — so an embedded host or MCP server can build the same bundle.

Mutation through a policy is intentionally avoided: per-agent values that tests
and callers adjust at runtime (timeouts, retry knobs, token caps) are copied
onto the Agent itself, never shared through the bundle (a shared mutable object
would leak one agent's override into its siblings).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import HarnessConfig


class AgentPolicy:
    """Single source of per-agent construction knobs.

    Defaults mirror ``HarnessConfig`` exactly; there is deliberately no second
    hardcoded fallback dictionary (the old ``runtime if config else <n>``
    ladder drifted from config and is gone).
    """

    def __init__(
        self,
        *,
        # -- safety (loop) --
        safety_max_iterations: int = 400,
        repeated_call_limit: int = 5,
        repeated_recovery_attempts: int = 2,
        repeated_call_exempt_tools: tuple[str, ...] | list[str] | None = None,
        safety_timeout_seconds: float | None = 7200.0,
        disable_root_timeout: bool = True,
        # -- LLM call / retry --
        call_timeout_seconds: float | None = 500.0,
        retry_max_attempts: int = 4,
        rate_limit_max_attempts: int = 6,
        retry_base_delay_seconds: float = 1.0,
        retry_max_delay_seconds: float = 30.0,
        retry_jitter_seconds: float = 0.5,
        rate_limit_backoff_multiplier: float = 3.0,
        fallback_on_rate_limit: bool = True,
        # -- budget --
        max_agent_tokens: int | None = None,
        # -- context / behavior --
        active_turn_window: int = 50,
        stream_children: bool = True,
        iteration_warning_margin: int = 50,
        iteration_warning_attempts: int = 1,
        delegate_nudge_threshold: int = 8,
        delegate_nudge_attempts: int = 1,
        brief_nudge_attempts: int = 1,
        # -- loop-guard (near-identical) --
        near_identical_threshold: int = 3,
        near_identical_window: int = 6,
        near_identical_similarity: float = 0.6,
        near_identical_tools: tuple[str, ...] | list[str] | None = None,
        near_identical_warning_attempts: int = 2,
    ) -> None:
        self.safety_max_iterations = int(safety_max_iterations)
        self.repeated_call_limit = int(repeated_call_limit)
        self.repeated_recovery_attempts = int(repeated_recovery_attempts)
        self.repeated_call_exempt_tools: tuple[str, ...] = tuple(
            repeated_call_exempt_tools
            if repeated_call_exempt_tools is not None
            else ("status", "usage", "result_read", "result_bash",
                  "channels", "channel_info", "channel_read")
        )
        self.safety_timeout_seconds: float | None = safety_timeout_seconds
        self.disable_root_timeout = bool(disable_root_timeout)
        self.call_timeout_seconds: float | None = call_timeout_seconds
        self.retry_max_attempts = int(retry_max_attempts)
        self.rate_limit_max_attempts = int(rate_limit_max_attempts)
        self.retry_base_delay_seconds = float(retry_base_delay_seconds)
        self.retry_max_delay_seconds = float(retry_max_delay_seconds)
        self.retry_jitter_seconds = float(retry_jitter_seconds)
        self.rate_limit_backoff_multiplier = float(rate_limit_backoff_multiplier)
        self.fallback_on_rate_limit = bool(fallback_on_rate_limit)
        self.max_agent_tokens: int | None = (
            int(max_agent_tokens) if max_agent_tokens else None
        )
        self.active_turn_window = int(active_turn_window)
        self.stream_children = bool(stream_children)
        self.iteration_warning_margin = int(iteration_warning_margin)
        self.iteration_warning_attempts = int(iteration_warning_attempts)
        self.delegate_nudge_threshold = int(delegate_nudge_threshold)
        self.delegate_nudge_attempts = int(delegate_nudge_attempts)
        self.brief_nudge_attempts = int(brief_nudge_attempts)
        self.near_identical_threshold = int(near_identical_threshold)
        self.near_identical_window = int(near_identical_window)
        self.near_identical_similarity = float(near_identical_similarity)
        self.near_identical_tools: tuple[str, ...] = tuple(
            near_identical_tools if near_identical_tools is not None else ("bash",)
        )
        self.near_identical_warning_attempts = int(near_identical_warning_attempts)

    # -- construction ------------------------------------------------------

    @classmethod
    def from_config(cls, config: "HarnessConfig | None") -> "AgentPolicy":
        """Build the policy from a harness config; ``None`` yields the
        ``HarnessConfig()`` defaults — the single source of truth."""
        if config is None:
            return cls()
        s = config.safety
        llm = config.llm
        a = config.agent
        return cls(
            safety_max_iterations=s.max_iterations,
            repeated_call_limit=s.repeated_call_limit,
            repeated_recovery_attempts=s.repeated_recovery_attempts,
            repeated_call_exempt_tools=list(s.repeated_call_exempt_tools),
            safety_timeout_seconds=s.timeout_seconds,
            disable_root_timeout=s.disable_root_timeout,
            call_timeout_seconds=llm.call_timeout_seconds,
            retry_max_attempts=llm.retry_max_attempts,
            rate_limit_max_attempts=llm.rate_limit_max_attempts,
            retry_base_delay_seconds=llm.retry_base_delay_seconds,
            retry_max_delay_seconds=llm.retry_max_delay_seconds,
            retry_jitter_seconds=llm.retry_jitter_seconds,
            rate_limit_backoff_multiplier=llm.rate_limit_backoff_multiplier,
            fallback_on_rate_limit=llm.fallback_on_rate_limit,
            max_agent_tokens=s.max_agent_tokens,
            active_turn_window=a.active_turn_window,
            stream_children=a.stream_children,
            iteration_warning_margin=s.iteration_warning_margin,
            iteration_warning_attempts=s.iteration_warning_attempts,
            brief_nudge_attempts=s.brief_nudge_attempts,
            near_identical_threshold=s.near_identical_threshold,
            near_identical_window=s.near_identical_window,
            near_identical_similarity=s.near_identical_similarity,
            near_identical_tools=list(s.near_identical_tools),
            near_identical_warning_attempts=s.near_identical_warning_attempts,
        )

    # -- per-spawn decisions -----------------------------------------------

    def root_timeout(self) -> float | None:
        """Full-run wall-clock budget for a ROOT agent (parent is None). Returns
        None when ``disable_root_timeout`` is set (root runs until it finishes
        on its own); otherwise the configured budget."""
        return None if self.disable_root_timeout else self.safety_timeout_seconds

    def child_timeout(self) -> float | None:
        """Full-run wall-clock budget for a child agent."""
        return self.safety_timeout_seconds

    def agent_ctor_kwargs(self, *, timeout: float | None) -> dict:
        """The keyword arguments for ``Agent.__init__`` (or a subclass ctor with
        the same signature). ``timeout`` is the already-resolved per-spawn
        budget (root exemption applied by the caller via ``root_timeout``)."""
        return {
            "safety_max_iterations": self.safety_max_iterations,
            "repeated_call_limit": self.repeated_call_limit,
            "repeated_recovery_attempts": self.repeated_recovery_attempts,
            "repeated_call_exempt_tools": self.repeated_call_exempt_tools,
            "safety_timeout_seconds": timeout,
            "active_turn_window": self.active_turn_window,
            "stream_children": self.stream_children,
            "near_identical_threshold": self.near_identical_threshold,
            "near_identical_window": self.near_identical_window,
            "near_identical_similarity": self.near_identical_similarity,
            "near_identical_tools": self.near_identical_tools,
            "near_identical_warning_attempts": self.near_identical_warning_attempts,
            "iteration_warning_margin": self.iteration_warning_margin,
            "iteration_warning_attempts": self.iteration_warning_attempts,
            "delegate_nudge_threshold": self.delegate_nudge_threshold,
            "delegate_nudge_attempts": self.delegate_nudge_attempts,
            "brief_nudge_attempts": self.brief_nudge_attempts,
        }

    def post_construct(self, agent: "object") -> None:
        """Apply the post-construction values (CLI/tests/callers may override
        these per-agent at runtime, so they are NOT constructor args — they are
        copied onto the instance, never shared through the policy)."""
        agent.max_agent_tokens = self.max_agent_tokens
        agent._call_timeout_seconds = self.call_timeout_seconds
        agent.retry_max_attempts = self.retry_max_attempts
        agent.rate_limit_max_attempts = self.rate_limit_max_attempts
        agent.retry_base_delay_seconds = self.retry_base_delay_seconds
        agent.retry_max_delay_seconds = self.retry_max_delay_seconds
        agent.retry_jitter_seconds = self.retry_jitter_seconds
        agent.rate_limit_backoff_multiplier = self.rate_limit_backoff_multiplier
        agent.fallback_on_rate_limit = self.fallback_on_rate_limit

    # -- ramar rendering ---------------------------------------------------

    def limits_line(
        self, *, max_agent_tokens: int | None, timeout: float | None
    ) -> str:
        """Compact statement of an agent's configured runtime constraints (ramar).

        Surfaces an agent's own safety limits (``safety.max_agent_tokens``,
        ``safety.timeout_seconds``) to its parent via the delegate result and
        status snapshot, so the parent can brief real constraints and size the
        delegation to fit — instead of the child discovering a cap only when it
        is hit (uppdragstaktik: communicate the ramar up front). The agent
        passes the *per-agent* values (which may be overridden at runtime) so
        the policy stays a pure renderer; a host may subclass to rephrase or
        restrict the subset shown.
        """
        parts: list[str] = []
        if max_agent_tokens:
            parts.append(f"token cap {max_agent_tokens}")
        if timeout:
            parts.append(f"wall-clock {timeout:.0f}s")
        return "; ".join(parts)