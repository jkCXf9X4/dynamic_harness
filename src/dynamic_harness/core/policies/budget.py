"""Run-budget / cost-bound policy objects as composable policies.

The token-budget and wall-clock-bound decisions an agent's loop used to embed
inline (grant/deny for mid-run budget requests, the wall-clock run timeout, and
the total-token hard cap) live here so a host enforcing the same bounds — an MCP
scheduler, an embedded harness — reuses the identical decisions and phrasings.

Each policy decides; the agent keeps the enforcement clock (``time.monotonic``
bookkeeping, the ``asyncio.wait_for`` wrapper, the force-fail side effects).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BudgetVerdict:
    """Outcome of a ``BudgetPolicy.check`` call."""

    allowed: bool
    remaining: int | None  # tokens left under the cap (None when uncapped)
    message: str


class BudgetPolicy:
    """Decides whether a mid-run budget request fits under the hard cap.

    ``0``/``None`` ``max_agent_tokens`` means uncapped (as in
    ``safety.max_agent_tokens``), so any request is granted.
    """

    def __init__(self, *, max_agent_tokens: int | None = None) -> None:
        self.max_agent_tokens: int | None = (
            int(max_agent_tokens) if max_agent_tokens else None
        )

    def check(self, *, current: int, requested: int, reason: str) -> BudgetVerdict:
        if self.max_agent_tokens is None:
            return BudgetVerdict(
                allowed=True, remaining=None,
                message="uncapped — approved",
            )
        remaining = self.max_agent_tokens - int(current)
        if remaining >= int(requested):
            return BudgetVerdict(
                allowed=True,
                remaining=remaining,
                message=(
                    f"approved: {requested} tokens (≈{4 * requested} chars) fit "
                    f"with {remaining} tokens left under the cap."
                ),
            )
        return BudgetVerdict(
            allowed=False,
            remaining=remaining,
            message=(
                f"refused: requesting {requested} tokens would exceed the "
                f"{self.max_agent_tokens}-token cap ({remaining} left). "
                f"Delegate, prune stale turns, or report/escalate to stay "
                f"within budget."
            ),
        )

    @staticmethod
    def format_request_activity(
        *, agent_id: str, current_usage: int, requested: int, reason: str, verdict: BudgetVerdict
    ) -> dict:
        """The activity-event payload for a budget request (self-describing
        shape so handlers can render it without coupling to the runtime)."""
        return {
            "agent_id": agent_id,
            "current_usage": current_usage,
            "requested": requested,
            "reason": reason,
            "allowed": verdict.allowed,
            "remaining": verdict.remaining,
        }


class TimeoutPolicy:
    """Wall-clock run-budget decisions for one agent's whole run.

    Separate from ``llm.call_timeout_seconds`` (bounded per-request by the
    retry layer): this is the full-run wall clock ``safety.timeout_seconds``.
    """

    def __init__(self, *, timeout_seconds: float | None) -> None:
        self.timeout_seconds: float | None = timeout_seconds

    @property
    def enabled(self) -> bool:
        return self.timeout_seconds is not None

    def remaining_seconds(self, elapsed: float) -> float | None:
        """Seconds left in the budget, or None when uncapped."""
        if self.timeout_seconds is None:
            return None
        return max(0.0, self.timeout_seconds - elapsed)

    def exceeded(self, elapsed: float) -> bool:
        return self.enabled and elapsed > self.timeout_seconds

    @staticmethod
    def timeout_message(
        timeout_seconds: float, iteration: int, mid_call: bool = False
    ) -> str:
        suffix = ", an LLM call exceeded the budget" if mid_call else ""
        return (
            f"Agent timed out after {timeout_seconds}s "
            f"({int(iteration)} iterations{suffix})"
        )


class TokenBudgetPolicy:
    """Per-agent total-token cap decisions.

    The hard cap (``safety.max_agent_tokens``) force-fails the loop; this owns
    the check and the wording the agent's ``_safety_check`` applies. The
    ``[Budget]`` guidance block folded into the system prompt is also here so
    the model sees the same limit the loop enforces.
    """

    def __init__(self, *, max_agent_tokens: int | None = None) -> None:
        self.max_agent_tokens: int | None = (
            int(max_agent_tokens) if max_agent_tokens else None
        )

    def exceeded(self, current: int) -> bool:
        return self.max_agent_tokens is not None and current > self.max_agent_tokens

    def exceed_message(self, current: int) -> str:
        return (
            f"Token budget exceeded: {current} > {self.max_agent_tokens} "
            f"total tokens. This agent stopped to contain cost."
        )

    def budget_guidance(self) -> str | None:
        """The static ``[Budget]`` block folded into the system prompt."""
        if self.max_agent_tokens is None:
            return None
        return (
            f"[Budget] This agent may use at most {self.max_agent_tokens} total "
            f"tokens (prompt + completion) before the run is stopped. Track your "
            f"live spend and messages with the usage tool; to stay lean, "
            f"delegate or prune stale turns instead of chaining calls in-context."
        )

    def timeout_guidance(self, timeout_seconds: float | None) -> str | None:
        """The static ``[Budget]`` wall-clock block folded into the system prompt.

        Communicates the agent's own wall-clock ramar up front (uppdragstaktik:
        the subordinate should know its limits, not discover them when the run
        is force-failed). ``None``/``0`` means no cap — no block is emitted.
        """
        if not timeout_seconds:
            return None
        return (
            f"[Budget] This agent has a {timeout_seconds:.0f}s wall-clock budget "
            f"before the run is force-failed. The clock is not directly "
            f"observable, so pace work: delegate independent units and "
            f"checkpoint after each milestone instead of chaining long serial "
            f"calls."
        )