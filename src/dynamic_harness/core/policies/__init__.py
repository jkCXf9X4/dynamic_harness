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
- ``ResumePlanner`` — decision half of the parent resume ladder (strategy
  validation, rot refusal, layer ordering, budget messages).
- ``AgentPolicy``   — single source of per-agent construction knobs (safety,
  retry, budget, context) built once from config.
- ``RetryPolicy``   — per-failure-class LLM retry/backoff decisions.
- ``DisclosurePolicy`` — progressive-disclosure tier building + selection.
- ``CostPolicy``    — USD cost conversion from per-1M-token prices (G9).
- ``BudgetPolicy``  — grant/deny for mid-run budget requests (G8).
- ``VerifyPolicy``  — mechanical acceptance-term gate for child output (G1).
- ``delegate_target_signature`` — canonical same-target key (host-agnostic).
"""

from __future__ import annotations

from .agent import AgentPolicy
from .budget import BudgetPolicy, BudgetVerdict, TimeoutPolicy, TokenBudgetPolicy
from .context import ContextMetricPolicy
from .cost import CostPolicy
from .disclosure import DisclosurePolicy
from .filesystem import SandboxPolicy
from .heal import HealBudget, HealPolicy, ResumePlanner
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
from .network import WebFetchPolicy
from .nudge import NudgeDecision, NudgePolicy
from .permissions import ToolPermissionPolicy
from .process import BashSafetyPolicy
from .result_cache import ResultCachePolicy
from .retry import RetryPolicy
from .spawn import SpawnDecision, SpawnPolicy
from .verify import VerifyPolicy, VerifyResult

__all__ = [
    "AgentPolicy",
    "BashSafetyPolicy",
    "BudgetPolicy",
    "BudgetVerdict",
    "ContextMetricPolicy",
    "CostPolicy",
    "DisclosurePolicy",
    "HealBudget",
    "HealPolicy",
    "LoopAction",
    "LoopGuard",
    "NudgeDecision",
    "NudgePolicy",
    "ResumePlanner",
    "ResultCachePolicy",
    "RetryPolicy",
    "SandboxPolicy",
    "SpawnDecision",
    "SpawnPolicy",
    "TimeoutPolicy",
    "TokenBudgetPolicy",
    "ToolPermissionPolicy",
    "VerifyPolicy",
    "VerifyResult",
    "WebFetchPolicy",
    "bash_family",
    "bash_read_regions",
    "delegate_target_signature",
    "normalize_tool_signature",
    "paginationless_signature",
    "regions_overlap",
    "similarity",
]