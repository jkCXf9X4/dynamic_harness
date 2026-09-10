"""Delegation-cap policy as a composable policy object.

``Runtime.delegate()`` was the single choke point through which every spawn —
roots, children, and self-heal fresh restarts — had to pass. The three caps
(``max_agents`` / ``max_depth`` / ``max_same_target_delegations``) and the
budget/warning *wording* live here as a pure policy; the runtime keeps the
``SpawnLedger`` counter (``core/spawn_limits.py``) that feeds it.

Moving the decisions here makes the caps reproducible and testable without a
runtime, and gives a plugin host (MCP server / extension) the same refusal
messages a harness event hook would surface.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


def delegate_target_signature(description: str) -> str:
    """Normalized key for a delegate call, keyed on the referenced path(s).

    Catches both failure modes observed in production:

    1. Orchestrators re-hire a fresh sub-agent to *read the same file* with
       superficially different wording ('read X verbatim' → 'read X from offset
       N' → ...), and
    2. Same-target *directory* drilling: an 'Explore the repository at
       /abs/path' agent that keeps delegating an identical 'explore that same
       root' task one level deeper each time until the tree runs away.

    Returns a ``|``-joined, sorted set of absolute directory/file paths and
    dotted relative file paths found in the description; falls back to the
    stripped description itself when no path is present.
    """
    if not description:
        return ""
    paths: list[str] = []
    # Absolute paths (files OR bare directory roots, e.g. /home/u/proj/repo).
    # The boundary lookbehind stops slash-adjacent words inside phrases like
    # 'failure/report' or 'read/verify' from being misread as absolute paths.
    for p in re.findall(r"(?<![A-Za-z0-9_./])/[\w./\-]+", description):
        if len(p) > 3:
            paths.append(p)
    # Dotted relative file paths (docs/roadmap/x.md).
    paths.extend(
        re.findall(
            r"(?<![A-Za-z0-9])(?:[\w./\-]+\.(?:md|txt|py|json|yaml|yml|toml|log))",
            description,
        )
    )
    unique = sorted(set(paths))
    return "|".join(unique) if unique else description.strip()


@dataclass(frozen=True)
class SpawnDecision:
    """Outcome of a ``SpawnPolicy.check`` call."""

    allowed: bool
    reason: str | None = None


class SpawnPolicy:
    """Decides whether a delegation may proceed and how to describe the caps.

    ``0``/``None`` on any limit disables that cap (harness.json convention).
    """

    #: Fraction of a cap at which the near-cap notice fires.
    WARNING_FRACTION: float = 0.8

    def __init__(
        self,
        *,
        max_agents: int | None = 200,
        max_depth: int | None = 15,
        max_same_target: int | None = 7,
        warning_attempts: int = 2,
    ) -> None:
        self.max_agents = max_agents
        self.max_depth = max_depth
        self.max_same_target = max_same_target
        self.warning_attempts: int = max(int(warning_attempts), 0)

    def check(
        self,
        *,
        agents_spawned: int,
        depth: int,
        same_target_count: int = 0,
        same_target_signature: str = "",
    ) -> SpawnDecision:
        """Return allowed, or refused with the exact refusal message.

        Checks run in the same order the runtime used to: total agents, then
        tree depth, then the per-lineage same-target count.
        """
        if self.max_agents is not None and agents_spawned >= self.max_agents:
            return SpawnDecision(
                False,
                f"agent limit reached: {self.max_agents} agents have been spawned "
                f"this run. Do NOT delegate more work — finish whatever is "
                f"naturally closable in-context, return remaining items to your "
                f"parent, and report/escalate/fail.",
            )
        if self.max_depth is not None and depth > self.max_depth:
            return SpawnDecision(
                False,
                f"tree depth limit reached: this delegation would be at depth "
                f"{depth} (max {self.max_depth}). The task hierarchy is too deep — "
                f"do NOT recurse further; solve the remaining work in-context, "
                f"return it to your parent, or escalate.",
            )
        if self.max_same_target is not None and same_target_count >= self.max_same_target:
            return SpawnDecision(
                False,
                f"target delegation limit reached: '{same_target_signature}' has "
                f"already been delegated {same_target_count} times along this "
                f"lineage (max {self.max_same_target}). Repeatedly re-delegating "
                f"the same target returns no new information and looks like a "
                f"loop. Verify the existing child's failure/report, solve it "
                f"in-context, or escalate — do NOT spawn another identical "
                f"sub-agent.",
            )
        return SpawnDecision(True)

    # -- wording helpers (fed by runtime.spawn_usage) --------------------

    def budget_line(self, usage: dict[str, Any]) -> str:
        """Compact delegation-cap status appended to every delegate() result.

        Lets the model self-regulate BEFORE a refusal: it sees how many agents
        have been spawned (vs ``max_agents``), its tree depth (vs
        ``max_depth``), and the most re-delegated target along its lineage (vs
        ``max_same_target_delegations``). Cf. the non-fatal near-cap notice.
        """
        parts: list[str] = []
        max_agents = usage.get("max_agents")
        if max_agents:
            parts.append(f"agents {usage['agents']}/{max_agents}")
        max_depth = usage.get("max_depth")
        if max_depth:
            parts.append(f"depth {usage['depth']}/{max_depth}")
        max_same = usage.get("max_same_target")
        if max_same and usage.get("top_same_targets"):
            top = usage["top_same_targets"][0]
            parts.append(
                f"top repeated target '{top['target'][:40]}' "
                f"{top['count']}/{max_same}"
            )
        return (
            f"[delegation budget] {'; '.join(parts) or 'uncapped'} — stop "
            "spawning and finish in-context / escalate as you near any cap."
        )

    def near_cap_warnings(self, usage: dict[str, Any], *, depth: int) -> list[str]:
        """List of caps that are at 80%+ used, for the near-cap notice.

        Mirrors live ``spawn_usage`` data plus the caller's tree depth.
        """
        warnings: list[str] = []
        max_agents = usage.get("max_agents")
        if max_agents:
            used = usage["agents"]
            if used and used >= max_agents * self.WARNING_FRACTION:
                warnings.append(f"total agents {used}/{max_agents}")
        max_depth = usage.get("max_depth")
        if max_depth:
            if depth >= max_depth * self.WARNING_FRACTION:
                warnings.append(f"tree depth {depth}/{max_depth}")
        max_same = usage.get("max_same_target")
        if max_same:
            for t in (usage.get("top_same_targets") or []):
                if t["count"] >= max_same * self.WARNING_FRACTION:
                    warnings.append(
                        f"target '{t['target'][:50]}' "
                        f"delegated {t['count']}/{max_same} times"
                    )
                    break
        return warnings

    @staticmethod
    def near_cap_note(warnings: list[str]) -> str:
        """The user-facing notice injected when near a cap."""
        return (
            "You are approaching the delegation caps: "
            + ", ".join(warnings)
            + ". 80% or more of a cap is used. Do NOT keep spawning sub-agents: "
            "stop expanding the tree, verify the children you already have, "
            "finish what is naturally closable in-context, return the remainder "
            "to your parent, and report / escalate / fail. A further refusal "
            "will NOT create an agent — it will only come back as an error."
        )