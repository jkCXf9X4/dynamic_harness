---
title: "Plugin Direction — Policy-Seam Breadth Audit"
category: investigation
parent: "README.md"
summary: >
  Consumers of each decision policy, and how the shared/domain split holds.
---

# 2. Policy seams (decision objects + reactive)

Consumers of `core/policies/` by host component:

| Policy | Consumed by | Via |
|--------|-------------|-----|
| `AgentPolicy` | Runtime | `Runtime.__init__` → `from_config` |
| `SpawnPolicy` / `SpawnWarningPolicy` | Runtime / Agent | construction + delegate choke point |
| `HealPolicy` / `HealBudget` / `ResumePlanner` | Runtime / Agent | self-heal + resume |
| `LoopGuard` (+ helpers) | Agent | `_run_loop` |
| `RetryPolicy` / `TimeoutPolicy` / `TokenBudgetPolicy` | Agent | LLM call / loop |
| `NudgePolicy` | Agent | low-iteration / delegate nudges |
| `ToolPermissionPolicy` | Runtime, ToolRegistry, agents tool | role gating |
| `ResultCachePolicy` | ToolRegistry | snapshot/render |
| `DisclosurePolicy` | Runtime, agents, artifacts | progressive disclosure; `deliver_report` + tools |
| `BashSafetyPolicy` | process, result_bash | bash guard |
| `WebFetchPolicy` | network | fetch guard |
| `SandboxPolicy` | filesystem | path containment |
| `ContextMetricPolicy` | AgentContext, ToolContext | token estimate + compress prompt |
| `ReactivePolicy` / `Observation` / `PromptInjection` / `Registry` | Agent loop; Runtime factory registration | the reference seam |

The split matches the ruling: **shared concerns → registry/runtime choke point**
(permissions, result-cache, disclosure) and **domain concerns → tool-embedded
policy objects** (bash-safety, webfetch, sandbox). Nothing imports an agent or
runtime; the interfaces hold.
