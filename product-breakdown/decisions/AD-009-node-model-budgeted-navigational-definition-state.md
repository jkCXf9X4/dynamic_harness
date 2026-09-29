---
id: AD-009
title: Node Model — Budgeted, Navigational Definition State
date: 2026-09-23
status: accepted
layers: [architecture]
state: README.md
artifacts:
  - product-breakdown/README.md
  - product-breakdown/tools/check_node_size.py
  - 3rd_party/agent_methods_and_tools/methods/product-breakdown/SKILL.md
  - docs/references/information_hygiene.md (storage-rules, readability-rules)
  - product-breakdown/05-operation/runbook/README.md
  - product-breakdown/**/*.md all (IMP-016)
supersedes: []
superseded_by: []
related: []
---

# AD-009: Node Model — Budgeted, Navigational Definition State

## Context
The definition state grew organically: 60+ files, largest 903 lines, index
READMEs carrying rationale, and one folder indexing by `index.md` while every
other uses `README.md`. Readers cannot tell on sight what is navigational versus
authoritative — the failure `information_hygiene.md` warns against. A sibling
deployment's convention (staging under `tmp/`) solved this with per-node size
budgets; this decision backports it.

## Decision
Every markdown file in `product-breakdown/` is a **node** with a budget enforced
by `product-breakdown/tools/check_node_size.py --strict`.

- **Index node** (one per folder, `README.md`): navigational only — purpose,
  owns/excludes, a `link → one-line description` table, decisions pointer. No
  rationale or detail. Target ≤40 lines, hard cap 75.
- **Leaf node**: one concern; target ≤50 lines, hard cap 75, minimum ~10.
- **Decision records**: small and decisive (≤~50 lines); never split — tighten
  or supersede.
- Over cap → **trim → link → split** along a concern seam; one canonical leaf
  per fact. Name files by role; folder indexes are `README.md`.
- The transition used a temporary allow-list of oversized nodes, refactored
  under IMP-016; it is now empty and removed, so `--strict` enforces the budget
  with no exemptions.

## Rationale
The definition state grew organically to 60+ files with no way to tell navigational from authoritative content — the failure information hygiene warns against. Per-node size budgets (index/leaf/record) make structure legible and canonical, enforced mechanically so a violation is a blocker instead of a style note.

## Alternatives Considered
- **No cap / judgment only** — REJECTED: judgment produced the drift; a
  mechanical check is what holds.
- **Immediate all-at-once enforcement** — REJECTED: forces rewriting 60+ nodes;
  a phased transition kept state usable while it converged.
- **Keep `index.md` for the divergent folder** — REJECTED: two names for one
  role is the ambiguity this removes.

## Consequences
**Positive:** index nodes become scannable; leaves stay single-concern; the
budget mechanizes information hygiene; one index name removes a lookup exception.

**Negative:** adoption initially left 52 overweight nodes (to 903 lines) and the
8 ADRs (93–121) out of budget; IMP-016 completed the phased refactor
(2026-09-23) and the temporary allow-list is removed.

## Verification
`check_node_size.py --strict` passes with zero violations and no allow-list
(IMP-016 landed 2026-09-23); the registers (`decision-log.md`,
`traceability-map.md`) reflect this decision.

## Review Trigger
When the definition state next changes materially, re-confirm the budget size
(IMP-016 completed 2026-09-23 and removed the allow-list mechanism).
