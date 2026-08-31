from __future__ import annotations

import re


class DelegationLimit(Exception):
    """Raised by ``Runtime.delegate`` when a spawn cap is hit.

    Carries a human-readable ``reason`` (the specific cap that was reached) so
    callers — the ``delegate`` tool and self-heal — can surface it to the model /
    parent instead of constructing an agent that should never exist.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


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


class SpawnLedger:
    """Per-lineage count of delegations aimed at the same target signature.

    A single ``SpawnLedger`` instance is inherited from a parent to all of its
    descendants (root → grandchildren → ...), so every worker along one lineage
    shares the same counter. This makes the same-target cap *lineage-scoped*:
    two unrelated branches exploring two different repositories can each use the
    full budget, while a single chain that keeps re-delegating 'explore the same
    repo' — even across self-heal restarts, which reset the in-context loop
    deques — trips the cap and is refused at the runtime choke point.
    """

    __slots__ = ("_target_counts",)

    def __init__(self) -> None:
        self._target_counts: dict[str, int] = {}

    def count(self, signature: str) -> int:
        return self._target_counts.get(signature, 0)

    def record(self, signature: str) -> int:
        if not signature:
            signature = "<no-target>"
        self._target_counts[signature] = self._target_counts.get(signature, 0) + 1
        return self._target_counts[signature]

    def top_targets(self, limit: int = 5) -> list[tuple[str, int]]:
        return sorted(
            self._target_counts.items(), key=lambda kv: kv[1], reverse=True
        )[:limit]

    def target_counts(self) -> dict[str, int]:
        return dict(self._target_counts)

    def total_recorded(self) -> int:
        return sum(self._target_counts.values())