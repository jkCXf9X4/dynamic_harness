---
id: INFO-189
type: info
title: "Plugin Direction — Investigation Next Steps"
category: investigation
parent: "README.md"
summary: >
  The completed checklist that carried the direction from question to
  implemented pilot seam.
date: 2026-09-28
status: current
---

# Investigation next steps

- [x] Decide the goal: interface economy (decouple + isolate + minimize
      interfaces); loader/late-injection explicitly out of scope
- [x] Record decisions Q1–Q5 (purpose / minimal manifest / crash loudly /
      default safety / code-only config)
- [x] Resolve the open questions into rulings (`INFO-191`): ToolContext
      single+narrowed, policy application split (registry-delegated shared /
      tool-embedded domain), no stdlib descriptor conversion, no discovery in
      tests, ~7 common-interface target set
- [x] Enumerate every registration call site (`register_default_tools`,
      `register_agent_class`, `register_reactive_policy`, `on_*` handlers,
      `set_llm`, CLI wiring) into one canonical "what the host accepts" map —
      implemented as `Runtime.installed_components()` + `EventBus.handler_counts()`
      (single introspection surface, no registry-internal reach)
- [x] List every common interface + its consumers + its breadth — see
      `INFO-181`, `INFO-180`,
      `INFO-179`: ~7 contracts hold; `ToolContext`
      maps member-by-member; the single-consumer authority cluster is the only
      latent split point; `message_count` is dead surface
- [x] Audit the observed couplings: `ToolContext` façade surface, `compress`
      prompt inline in the façade, tool-level policy imports, direct actor
      reach from `ToolContext.status`/`kill`/`converse`
- [x] Ruling: keep ONE ToolContext, narrowed (facet rejected — multiplies
      interfaces)
- [x] Ruling: policy application = registry-delegated shared / tool-embedded
      domain policies, no mega-interface
- [x] Ruling: no discovery boundary needed — tests inject explicitly
- [x] **IMPLEMENTED** — pilot seam (policies + ToolContext narrowing):
      compress prompt moved into `ContextMetricPolicy.COMPRESS_PROMPT`,
      private `agent._archived_artifact_ids` reach replaced with public
      `Agent.record_archived_artifact`, `usage_summary` moved onto public
      `Agent.usage_summary` (no `_runtime`/`_iteration` reach), `pytest`
      green (466 passed)
- [x] **IMPLEMENTED** — dead surface trimmed: `ToolContext.message_count`
      removed (no tool/test consumer; `Agent.message_count` remains public),
      per the audit's trimming rule; `pytest` green (466 passed)
- [x] Write the success criteria: ~7 stable interfaces + no outside
      private-state reach + zero regressions on `pytest`; stdlib conversion
      stays off the table
- [x] Compare with the two reference plugin-centric designs — OpenCode V2
      (domain transforms + runtime hooks) and DeepSeek Harness
      (everything-is-a-plugin on Cordis); see
      `INFO-184`. Verdict: seam-first /
      no-loader is validated; both references are the same contract economy
      plus platform machinery.
- [x] Compare how the references build and work with **context** to enable
      plugin-centricity — see `INFO-182`.
      Verdict: both make context a contribution space (ordered, scoped,
      disposable), matching the harness's reactive-policy shape; the single
      material gap is per-agent registration scoping.
- [ ] **Adopt — one registration contract.** Ordered add → `dispose()` handle
      across tool/policy/handler/agent-class registries (narrows the seams;
      count stays ≈7; no loader implied). Include an optional **per-agent
      scope key** (dsh `agent.ctx` pattern), so a policy/tool/context
      contributor can be bound to one agent; lands inside the existing
      metric-reactive seam, not a new interface.
- [ ] **Adopt — per-request tool snapshot.** Freeze the schema↔executor map
      for the duration of a model request so mid-loop registry mutation cannot
      desync model↔executor.
