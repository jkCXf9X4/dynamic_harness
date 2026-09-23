---
title: "Plugin Direction — Resolved Rulings 1–4"
category: investigation
parent: "README.md"
summary: >
  ToolContext single+narrowed, policy-application split, no stdlib descriptor
  conversion, no discovery in tests.
---

# Resolved rulings (Q1–Q5 filled per direction)

1. **ToolContext: single contract, narrowed — NOT faceted.** Faceting would
   *multiply* the common-interface count, contradicting the primary goal
   ("minimize common interfaces"). Keep ONE `ToolContext` contract (count
   stays 1) and *narrow it*: move policy-ish logic out (the inline `compress`
   prompt → `ContextMetricPolicy`), replace direct private-state reaches
   (`record_archived_artifact` appending to `agent._archived_artifact_ids` →
   public `Agent` method), and document exactly what tools may touch. Tools
   state their needs in terms of the single public contract, never in terms of
   agent internals.
2. **Policy application path: registry-delegated for shared concerns,
   tool-embedded policy objects for domain guards.** No unified
   "policy-runner" mega-interface (that would be one more common interface).
   Shared every-tool concerns stay at the registry/runtime choke point
   (permissions, result-cache, truncation — already true). Tool-*specific*
   guards (sandbox, bash-safety, webfetch, disclosure) keep living in the tool,
   but always as host-agnostic policy objects invoked by it — never as inline
   logic or agent/runtime imports (already true; the inline `compress` prompt
   in the façade is the exception being fixed).
3. **Stdlib conversion: NOT a prerequisite.** There is no loader, so
   "defaults" means "registered through the public register calls the same way
   anything else would be" — already the case (`register_default_tools`,
   `register_agent_class`, `register_reactive_policy`). Built-ins are
   conceptually "the standard library"; no descriptor conversion adds value
   until the contracts are proven. Pilot seam = policies, demonstrated through
   the existing reactive registry.
4. **Deterministic tests: no discovery, ever.** Since no loader is built, there
   is *no* filesystem/ambient discovery boundary — none to design. Mock-LLM
   tests inject their components explicitly (construct policies / register
   tools on a fresh `Runtime`), exactly as they do today. This stays a hard
   rule: component lists are explicit or default; they are never scanned.
