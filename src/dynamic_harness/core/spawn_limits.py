from __future__ import annotations

# Back-compat re-export: the canonical implementation now lives in the
# host-agnostic policies package (core/policies/spawn.py). Kept so existing
# ``from dynamic_harness.core.spawn_limits import delegate_target_signature``
# callers keep working.
from .policies.spawn import delegate_target_signature as delegate_target_signature  # noqa: F401


class DelegationLimit(Exception):
    """Raised by ``Runtime.delegate`` when a spawn cap is hit.

    Carries a human-readable ``reason`` (the specific cap that was reached) so
    callers — the ``delegate`` tool and self-heal — can surface it to the model /
    parent instead of constructing an agent that should never exist.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


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