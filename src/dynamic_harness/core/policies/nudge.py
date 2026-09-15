"""Notice injection policy as a composable policy object.

The agent's soft, non-fatal nudges — "you have not delegated any work" and
"your iteration budget is almost exhausted" — each had a fire-condition and a
fixed message baked into the agent loop. This policy owns the conditions, the
message text, AND (as a ``ReactivePolicy``) the per-instance warning budgets,
so a plugin host injecting the same guidance (or a host that wants different
thresholds) reuses the identical phrasing without importing an agent.

The policy decides WHETHER to fire and WHAT to say; the agent owns the
tail-append + activity-event side effects.
"""

from __future__ import annotations

from dataclasses import dataclass

from .interface import Observation, PromptInjection, ReactivePolicy


@dataclass(frozen=True)
class NudgeDecision:
    """A nudge to inject, or ``fire=False`` when none should fire."""

    fire: bool
    warning_type: str
    note: str | None = None
    data: dict | None = None


class NudgePolicy(ReactivePolicy):
    """Conditions + wording for the loop's soft guidance messages.

    All three nudges are tail-append-only and budgeted: they fire at most
    ``attempts`` times, never mutate a prior message, and never fail the run
    (the prompt prefix — and the provider's cache contiguity — stays intact).

    As a ``ReactivePolicy`` the instance owns its remaining attempt budgets
    (``delegate_nudge_left`` / ``iteration_warning_left``); ``evaluate``
    consults them and the pure ``delegate_nudge``/``iteration_warning``
    decisions, decrementing a budget when a nudge fires.
    """

    name: str = "nudges"

    def __init__(
        self,
        *,
        delegate_nudge_threshold: int = 8,
        delegate_nudge_attempts: int = 1,
        iteration_warning_margin: int = 50,
        iteration_warning_attempts: int = 1,
        safety_max_iterations: int = 400,
    ) -> None:
        self.delegate_nudge_threshold: int = max(int(delegate_nudge_threshold), 1)
        self.delegate_nudge_attempts: int = max(int(delegate_nudge_attempts), 0)
        self.iteration_warning_margin: int = max(int(iteration_warning_margin), 1)
        self.iteration_warning_attempts: int = max(int(iteration_warning_attempts), 0)
        self.safety_max_iterations: int = max(int(safety_max_iterations), 1)
        self.delegate_nudge_left: int = self.delegate_nudge_attempts
        self.iteration_warning_left: int = self.iteration_warning_attempts

    def reset(self) -> None:
        """Restore the warning budgets (fresh run / interactive resume)."""
        self.delegate_nudge_left = self.delegate_nudge_attempts
        self.iteration_warning_left = self.iteration_warning_attempts

    # -- reactive policy entry point ----------------------------------------

    def evaluate(self, observation: Observation) -> list[PromptInjection]:
        """React to an observation: return every nudge that must fire.

        Checks the delegate-reminder first, then the low-iteration wrap-up (the
        historical application order), each consuming its own attempt budget.
        """
        out: list[PromptInjection] = []
        d = self.delegate_nudge(
            iteration=observation.iteration,
            attempts_left=self.delegate_nudge_left,
            has_delegated=observation.has_delegated,
        )
        if d.fire:
            self.delegate_nudge_left -= 1
            out.append(self._to_injection(d))
        d = self.iteration_warning(
            iteration=observation.iteration,
            attempts_left=self.iteration_warning_left,
        )
        if d.fire:
            self.iteration_warning_left -= 1
            out.append(self._to_injection(d))
        return out

    @staticmethod
    def _to_injection(decision: NudgeDecision) -> PromptInjection:
        return PromptInjection.warning(
            decision.note or "",
            warning_type=decision.warning_type,
            data=decision.data,
        )

    # -- delegate-rarity nudge --------------------------------------------

    def delegate_nudge(
        self,
        *,
        iteration: int,
        attempts_left: int,
        has_delegated: bool,
    ) -> NudgeDecision:
        """One-off reminder when an agent reaches many turns without delegating."""
        if has_delegated or attempts_left <= 0 or iteration < self.delegate_nudge_threshold:
            return NudgeDecision(fire=False, warning_type="delegate_reminder")
        note = (
            f"You are {iteration} turns into this run and have not delegated any "
            "work. If your task decomposes into independent units, delegate them "
            "to fresh sub-agents in one turn and verify each by artifact summary. "
            "If the task is genuinely atomic and effectively done, prune stale "
            "committed turns to keep context flat, then report / escalate / fail "
            "instead of chaining further calls in-context."
        )
        return NudgeDecision(
            fire=True,
            warning_type="delegate_reminder",
            note=note,
            data={
                "turn": iteration,
                "attempts_remaining": attempts_left - 1,
            },
        )

    # -- iteration wrap-up nudge -------------------------------------------

    def iteration_warning(
        self, *, iteration: int, attempts_left: int
    ) -> NudgeDecision:
        """ONE hard wrap-up notice when remaining iterations are running low."""
        if attempts_left <= 0:
            return NudgeDecision(fire=False, warning_type="iterations_running_low")
        remaining = self.safety_max_iterations - iteration
        # A margin >= max would make ``remaining <= margin`` true from the very
        # first turn, firing the wrap-up notice spuriously every turn. Cap the
        # effective margin below the limit so the notice only fires once the
        # agent has actually started consuming its iteration budget.
        margin = min(self.iteration_warning_margin, self.safety_max_iterations - 1)
        if remaining > margin:
            return NudgeDecision(fire=False, warning_type="iterations_running_low")
        remaining = max(remaining, 0)
        note = (
            "Your iteration budget is almost exhausted: you have roughly "
            f"{remaining} iterations left before the hard limit at "
            f"{self.safety_max_iterations} (you are on iteration "
            f"{iteration}). Stop starting new work. Finish whatever is "
            "naturally closable right now. For anything you cannot complete, "
            "return the remaining items and all relevant intermediate context "
            "(discoveries, file paths, partial results, and what the parent "
            "would need to pick this up) to your parent, and report / escalate / "
            "fail as appropriate so the parent can decide what is reasonable to "
            "finish off in other tasks."
        )
        return NudgeDecision(
            fire=True,
            warning_type="iterations_running_low",
            note=note,
            data={
                "iteration": iteration,
                "remaining": remaining,
                "limit": self.safety_max_iterations,
                "attempts_remaining": attempts_left - 1,
            },
        )