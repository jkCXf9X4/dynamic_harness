"""Mission-command brief-completeness nudge as a composable policy object.

The mission-command delegation methodology
(``skills/mission-command/SKILL.md``) asks parents to brief each
child with at least ``intent`` + ``end_state`` (the dimensions a child needs to
keep deciding correctly when conditions change). That guidance lives in the
optimized system prompt, but nothing *observes* it: a parent can delegate WHAT
without WHY and nothing corrects it. This policy closes the gap as a
``ReactivePolicy``: it watches every ``delegate`` tool call in the post-turn
observation and, on a per-run budget, injects a notice naming the missing
brief dimension(s).

Host-agnostic by construction — imports neither an agent nor a runtime. A
plugin host can register, replace, or rephrase this policy through the shared
reactive-policy seam (``ReactivePolicyRegistry`` / runtime
``register_reactive_policy``) without touching the run loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .interface import Observation, PromptInjection, ReactivePolicy

# The brief dimensions a child needs to adapt correctly when conditions change.
_REQUIRED = ("intent", "end_state")


@dataclass(frozen=True)
class BriefDecision:
    """A brief nudge to inject, or ``fire=False`` when none should fire."""

    fire: bool
    warning_type: str = "mission_brief"
    note: str | None = None
    data: dict | None = None


class BriefPolicy(ReactivePolicy):
    """Watch ``delegate`` calls for the mission-command intent dimension.

    Fires at most ``brief_nudge_attempts`` times per run (default 1), and only
    on turns where at least one ``delegate`` call lacks ``intent`` or
    ``end_state``. One notice per turn regardless of how many under-briefed
    children were spawned, and never fails the run (tail-append-only, so the
    prompt prefix — and the provider's cache contiguity — stays intact).
    """

    name: str = "mission_brief"

    def __init__(self, *, brief_nudge_attempts: int = 1) -> None:
        self.brief_nudge_attempts: int = max(int(brief_nudge_attempts), 0)
        self.brief_nudge_left: int = self.brief_nudge_attempts

    def reset(self) -> None:
        """Restore the notice budget (fresh run / interactive resume)."""
        self.brief_nudge_left = self.brief_nudge_attempts

    def evaluate(self, observation: Observation) -> list[PromptInjection]:
        if self.brief_nudge_left <= 0:
            return []
        decision = self.mission_brief_nudge(
            tool_calls=observation.tool_calls,
            attempts_left=self.brief_nudge_left,
        )
        if not decision.fire:
            return []
        self.brief_nudge_left -= 1
        return [PromptInjection.notice(
            decision.note or "",
            warning_type=decision.warning_type,
            data=decision.data,
        )]

    @staticmethod
    def mission_brief_nudge(
        *,
        tool_calls: list[Any],
        attempts_left: int,
    ) -> BriefDecision:
        """The pure decision: do any ``delegate`` calls lack intent/end_state?"""
        if attempts_left <= 0:
            return BriefDecision(fire=False)
        missing: list[str] = []
        for tc in tool_calls:
            if getattr(tc, "name", None) != "delegate":
                continue
            args = getattr(tc, "arguments", None) or {}
            for field in _REQUIRED:
                if not args.get(field) and field not in missing:
                    missing.append(field)
            if missing:
                break  # one turn, one notice
        if not missing:
            return BriefDecision(fire=False)
        return BriefDecision(
            fire=True,
            warning_type="mission_brief",
            note=(
                "[brief] A delegate() call is missing the mission-command intent "
                f"dimension ({', '.join(missing)}). Without it the child cannot "
                "decide correctly when conditions change. Add intent (why this "
                "matters — the child's decision criterion) and end_state (what "
                "'done' looks like); constraints/authority are optional but "
                "recommended."
            ),
            data={
                "missing": missing,
                "attempts_remaining": attempts_left - 1,
            },
        )