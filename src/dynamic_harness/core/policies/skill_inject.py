"""Proactive skill relevance — point an agent at its most relevant skill.

The static ``[Skills]`` trigger block (name + description) already sits in the
stable system-prompt prefix. It enumerates, but it cannot rank: a model facing
several triggers may never load the one that matters most for its task. This
policy adds the *relevance* signal — after the first turn it names the single
best-matching skill for the agent's task description, so the load happens
instead of being skipped.

The policy is host-agnostic: it imports neither an agent nor a runtime. It is
constructed with the skill library + the agent's role, reacts to an
``Observation`` carrying ``task_description``, and emits at most one ``notice``
injection per agent lifetime — bounded, cache-friendly, and never a delivery
mechanism (the body is still loaded via ``skill_load``).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from .interface import Observation, PromptInjection

if TYPE_CHECKING:
    from ..references import Skill


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9][a-z0-9_\-]*", text.lower()))


def _overlap_score(skill: "Skill", task_text: str) -> int:
    """Token overlap between a skill's name/description and the task text.

    Stopwords are deliberately not filtered: trigger descriptions are written to
    be matchable (e.g. "decision records, IMP candidates, decision log"), and a
    few generic hits are harmless because the policy surfaces at most one skill
    and requires a minimum score before it fires at all.
    """
    if not task_text:
        return 0
    task_tokens = _tokens(task_text)
    trigger_tokens = _tokens(skill.name) | _tokens(skill.description)
    return sum(1 for t in trigger_tokens if t in task_tokens)


class SkillInjectionPolicy:
    """Reactive policy recommending the single best-matching skill for a task.

    Only role-eligible skills are candidates (an unscoped skill applies to every
    role). Fires once per agent lifetime and only when a candidate's description
    overlaps the task enough to be worth naming.
    """

    name = "skill_injection"

    def __init__(
        self,
        skills: list["Skill"],
        *,
        role: str | None = None,
        min_score: int = 1,
    ) -> None:
        self._candidates: list["Skill"] = [s for s in skills if s.applies_to_role(role)]
        self._min_score = min_score
        self._surfaced = False

    def evaluate(self, observation: Observation) -> PromptInjection | None:
        if self._surfaced:
            return None
        task = observation.task_description or ""
        if not task:
            return None
        best: "Skill | None" = None
        best_score = 0
        for skill in self._candidates:
            score = _overlap_score(skill, task)
            if score > best_score:
                best, best_score = skill, score
        if best is None or best_score < self._min_score:
            return None
        self._surfaced = True
        return PromptInjection.notice(
            message=(
                f"[Skill] The skill most relevant to your task is '{best.name}': "
                f"{best.description} Load its full instructions with "
                f"skill_load('{best.name}')."
            ),
            warning_type="skill_hint",
            data={"skill": best.name},
        )