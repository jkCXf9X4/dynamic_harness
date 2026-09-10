"""Composable policy objects extracted from the agent loop / runtime.

These are the decision pieces behind the harness' mechanically enforced
guarantees, as standalone components that do not import an agent or runtime.
Each mirrors the exact behavior it was extracted from, so the runtime and the
agents now *delegate* to the same policies a plugin host (MCP server /
extension) would reuse.

- ``LoopGuard``     — repeated-call / near-identical loop detection + ladder.
- ``ResultCachePolicy`` — result-handle cacheability and paging-footers.
- ``SpawnPolicy``   — delegation caps (agents / depth / same-target) + wording.
- ``HealPolicy`` / ``HealBudget`` — blunt-vs-rot diagnosis, deliverable gate,
  shared heal budget, nudge/restart messages.
"""

from __future__ import annotations

from .heal import HealBudget, HealPolicy
from .loop_guard import (
    LoopAction,
    LoopGuard,
    bash_family,
    bash_read_regions,
    delegate_target_signature,
    normalize_tool_signature,
    paginationless_signature,
    regions_overlap,
    similarity,
)
from .result_cache import ResultCachePolicy
from .spawn import SpawnDecision, SpawnPolicy

__all__ = [
    "HealBudget",
    "HealPolicy",
    "LoopAction",
    "LoopGuard",
    "ResultCachePolicy",
    "SpawnDecision",
    "SpawnPolicy",
    "bash_family",
    "bash_read_regions",
    "delegate_target_signature",
    "normalize_tool_signature",
    "paginationless_signature",
    "regions_overlap",
    "similarity",
]