---
id: INFO-189
type: info
title: "Plugin Direction — Investigation Next Steps"
summary: >
  Open items for the plugin direction: one registration contract (with
  per-agent scope key) and a per-request tool snapshot.
date: 2026-09-28
status: current
---

# Plugin Direction — Investigation Next Steps

Open items. The completed checklist items now live in their canonical homes —
the `INFO-179`…`INFO-192` chain and `AD-007`.

- **Adopt — one registration contract.** Ordered add, then a `dispose()` handle
  across tool/policy/handler/agent-class registries (narrows the seams; count
  stays ≈7; no loader implied). Include an optional **per-agent scope key**
  (dsh `agent.ctx` pattern), so a policy/tool/context contributor can be bound
  to one agent; lands inside the existing metric-reactive seam, not a new
  interface.
- **Adopt — per-request tool snapshot.** Freeze the schema-to-executor map for
  the duration of a model request so mid-loop registry mutation cannot desync
  the model and executor.
