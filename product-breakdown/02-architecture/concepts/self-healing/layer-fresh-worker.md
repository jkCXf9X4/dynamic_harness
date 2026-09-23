# Layer 3 — Fresh Worker

Trigger: **context rot** — `repeated_call_limit` fired, `max_iterations`
reached, wall-clock timeout, or repeated Layer-1 misses. Resuming here would
replay the poisoned context. Instead, re-delegate a fresh agent over the same
task, but:

1. inject the prior failure reason into the new description, and
2. point it at on-disk artifacts the dead worker already produced.

This reconciles with disposable-worker economics: freshness fixes rot, disk
preserves partial progress. Budget: one retry; a second failure escalates.

A fresh worker spawn goes through the same `Runtime.delegate()` choke point as
every other agent, so it is bounded by the **delegation caps**
(`safety.max_agents` / `safety.max_depth` / `safety.max_same_target_delegations`).
When a cap refuses the spawn — e.g. the lineage has already re-delegated the same
target up to `max_same_target_delegations`, or the run has hit `max_agents` —
`_fresh_restart` emits a `fresh_refused` self-heal event and leaves the failed
agent in place (bounded out) rather than creating an agent that should never
exist. The parent sees the failed child via `status`/`resume` and decides whether
to fold its partial work in manually or escalate.
