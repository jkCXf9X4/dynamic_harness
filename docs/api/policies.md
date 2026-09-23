---
title: "Policies Reference"
category: api
module: dynamic_harness.core.policies
summary: >
  The host-agnostic decision layer extracted from Runtime / Agent /
  ToolRegistry during the policies refactor. Each policy decides; the caller
  (agent, runtime, or registry) performs the I/O. Reused by plugin hosts.
  See ../../product-breakdown/00-intent/platform-evaluation/README.md.
related:
  - runtime.md
  - agent.md
  - config.md
  - tools.md
  - ../../product-breakdown/00-intent/platform-evaluation/README.md
---

# Policies

```python
from dynamic_harness.core.policies import (
    AgentPolicy, SpawnPolicy, HealPolicy, HealBudget, ResumePlanner, LoopGuard,
    ResultCachePolicy, RetryPolicy, DisclosurePolicy, BudgetPolicy,
    TimeoutPolicy, TokenBudgetPolicy, CostPolicy, VerifyPolicy, NudgePolicy,
    ToolPermissionPolicy, BashSafetyPolicy, WebFetchPolicy, SandboxPolicy,
    ContextMetricPolicy,
)
```

These are the host-agnostic decision pieces behind the harness' mechanically
enforced guarantees, extracted from the agent loop / runtime / tool registry.
They **import neither an agent nor a runtime** — each mirrors the exact behavior
it was extracted from, and merely *decides* while the caller performs the side
effect (spawning, retrying, locking, saving, message injection). A plugin host
(MCP server / extension — see `../../product-breakdown/00-intent/platform-evaluation/README.md`) reuses the same
decisions and wording without coupling to the harness core.

| Policy | File | Purpose |
|--------|------|---------|
| `AgentPolicy` | `agent.py` | Per-agent construction knobs (safety, retry, budget, context) — the single config source for `Runtime.delegate()`. `from_config()` / `agent_ctor_kwargs()` / `post_construct()` / `root_timeout()`. |
| `SpawnPolicy` | `spawn.py` | Delegation caps (agents / depth / same-target) + refusal and budget/warning wording. |
| `HealPolicy` | `heal.py` | Layered self-heal decisions: blunt-vs-rot diagnosis, deliverable gate, resume/fresh message builders. |
| `HealBudget` | `heal.py` | Shared per-child used-counter for resume/fresh heal attempts (dict-like `can`/`bump`). |
| `ResumePlanner` | `heal.py` | Decision half of the parent-driven `resume` ladder: strategy validation, rot refusal, layer ordering, budget messages. |
| `LoopGuard` | `loop_guard.py` | Stateful repeated-call / near-identical loop detection + the nudge→fail recovery ladder (returns structured `LoopAction` verdicts). |
| `ResultCachePolicy` | `result_cache.py` | Result-handle cacheability (`DEFAULT_NON_CACHEABLE`) and token-window rendering / paging footers. |
| `RetryPolicy` | `retry.py` | Per-failure-class LLM retry/backoff: classification, budgets, exponential delay, `Retry-After` handling, session-pin drop. |
| `DisclosurePolicy` | `disclosure.py` | Progressive-disclosure tier building + selection (`views_from_report`, `build_view_dict`, `VIEW_LEVELS`, `reveal_fields` / `first_deeper_content`). |
| `BudgetPolicy` | `budget.py` | Grant/deny for mid-run token-budget requests (with a structured `BudgetVerdict`). |
| `TimeoutPolicy` | `budget.py` | Whole-run wall-clock (`safety.timeout_seconds`) decisions. |
| `TokenBudgetPolicy` | `budget.py` | Per-agent total-token hard cap (`safety.max_agent_tokens`) + the `[Budget]` system-prompt guidance. |
| `CostPolicy` | `cost.py` | USD cost conversion from per-1M-token prices (G9). |
| `VerifyPolicy` | `verify.py` | Mechanical acceptance-term scan over a child's artifact body (G1). |
| `NudgePolicy` | `nudge.py` | Conditions + wording for the delegate-rarity and low-iteration soft notices. |
| `ToolPermissionPolicy` | `permissions.py` | Role tool allow-lists (`ORCHESTRATOR_ALLOWED_TOOLS` / `ROLE_TOOL_OVERRIDES`) + agent-state eligibility (killable / conversable / resumable). |
| `BashSafetyPolicy` | `process.py` | Read-only-ness, shell-metacharacter detection, and leading-`cd` workdir resolution for the `bash` tool. |
| `WebFetchPolicy` | `network.py` | URL host validation (SSRF), fetch-size caps, and redirect budgets for `webfetch`. |
| `SandboxPolicy` | `filesystem.py` | Filesystem containment: safe-path resolution, sandbox root, hidden-file filtering. |
| `ContextMetricPolicy` | `context.py` | Token-estimation proxies (chars/words per token) and compress-retry counts. |

Supporting decisions also exported from the package: `SpawnDecision`,
`BudgetVerdict`, `VerifyResult`, `NudgeDecision`, `LoopAction`, and the pure
signature helpers (`delegate_target_signature`, `normalize_tool_signature`,
`bash_family`, `bash_read_regions`, `regions_overlap`, `similarity`).

## Where Each Policy Is Consumed

- **Runtime** builds `AgentPolicy`, `SpawnPolicy`, and `HealPolicy`
  (`HealBudget` per-child) in `__init__` and uses `DisclosurePolicy` in
  `deliver_report` (see `docs/api/runtime.md`).
- **Agent** owns/uses `LoopGuard`, `RetryPolicy`, `TimeoutPolicy` /
  `TokenBudgetPolicy`, `NudgePolicy`, `ToolPermissionPolicy`, and
  `ResumePlanner` (see `docs/api/agent.md`).
- **ToolRegistry** uses `ToolPermissionPolicy` (role gating) and
  `ResultCachePolicy` (cacheability + footers); the individual tools use
  `BashSafetyPolicy`, `WebFetchPolicy`, `SandboxPolicy`, `ContextMetricPolicy`,
  and `DisclosurePolicy` (see `docs/api/tools.md`).

Extension surface: construct one of these objects and either pass it into the
`Runtime`/`ToolRegistry`/agent, or subclass it — decisions that were not yet
extracted stay in `core/policies/` as new composable objects.