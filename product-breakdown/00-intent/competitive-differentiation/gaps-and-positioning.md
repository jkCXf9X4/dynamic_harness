---
title: "Gaps and Positioning"
category: meta
summary: >
  The two pillars where enforcement is not yet mechanized (verification G1,
  budgeting G8), the enforced/distinctive scoreboard, and the defensible
  "only-us" positioning.
parent: "README.md"
related:
  - ../../04-verification/gap-analysis/README.md
---

# Gaps and Positioning

## Honest open gaps

[Gap analysis](../../04-verification/gap-analysis/README.md) flags two pillars
where enforcement is *not yet* mechanized — the weakest differentiation claims
today:

- **G1 — Verification is prompt discipline, not a mechanism.** `plan` records
  acceptance criteria, but nothing mechanically evaluates them; "done" is what
  `report()` declares. "Verify before synthesize" is the least enforced pillar and
  the least differentiated from the field.
- **G8 — Budgeting/cost-control is dead plumbing.** `request_more_budget` and
  `on_budget_request` exist but no tool exposes them and there is no spend cap.
  The "#1 motivation" (cost) is not yet enforceable.

## Summary

Mechanically enforced and distinctive vs. the field:

- Near-identical bash/loop detection with fuzzy signatures
- Result caching behind opaque read-only handles
- Blunt-vs-rot self-healing with a shared heal budget
- Same-target spawn caps (per-lineage)
- Deliverable gate heals prose-completions

Mechanically enforced, closer to standard: checkpoint resume across restarts.

Not yet enforced (and therefore not distinctive): verify-before-synthesize (G1),
cost enforcement / budget (G8).

## Positioning

The defensible "only-us" claim: **fuzzy repeated-call safety, opaque result
handles, deterministic blunt-vs-rot recovery with a shared budget, and
same-target spawn limits** — mechanisms that keep working when the model stops
following the prompt.
