---
title: "Plugin Direction — Investigation Next Steps"
category: investigation
parent: "README.md"
summary: >
  The completed checklist that carried the direction from question to
  implemented pilot seam.
---

# Investigation next steps

- [x] Decide the goal: interface economy (decouple + isolate + minimize
      interfaces); loader/late-injection explicitly out of scope
- [x] Record decisions Q1–Q5 (purpose / minimal manifest / crash loudly /
      default safety / code-only config)
- [x] Resolve the open questions into rulings ([rulings.md](rulings.md)): ToolContext
      single+narrowed, policy application split (registry-delegated shared /
      tool-embedded domain), no stdlib descriptor conversion, no discovery in
      tests, ~7 common-interface target set
- [x] Enumerate every registration call site (`register_default_tools`,
      `register_agent_class`, `register_reactive_policy`, `on_*` handlers,
      `set_llm`, CLI wiring) into one canonical "what the host accepts" map —
      implemented as `Runtime.installed_components()` + `EventBus.handler_counts()`
      (single introspection surface, no registry-internal reach)
- [x] List every common interface + its consumers + its breadth — see
      [audit-tool-context.md](audit-tool-context.md), [audit-policies.md](audit-policies.md),
      [audit-other-seams.md](audit-other-seams.md): ~7 contracts hold; `ToolContext`
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
