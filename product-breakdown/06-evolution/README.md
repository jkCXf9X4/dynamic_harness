---
title: Layer 06 — Evolution
summary: What controlled changes come next?
---

# Layer 06 — Evolution

**What controlled changes come next?**

The evolution layer is the controlled-change register: the roadmap (`roadmap.md`) is the IMP-style canonical list of open work — each item with status (Proposed/Selected/Completed/Superseded), priority, evidence, and a task-contract seed — and `backlog.md` is the raw idea/suggestion log (the moved `__undeveloped_sugestions__.md`, now with disposition discipline). Selected IMPs are filed under `selected/` per the IMP template and cross-listed in the Implementation Status table below. An IMP is **a scoped candidate needing a task contract before code changes — not implementation approval.**

## Implementation Status

| IMP | Theme | Stage | Priority |
|-----|-------|-------|----------|
| [IMP-001](selected/IMP-001.md) | Comms benchmark P4 (topics_parent) replicates | Proposed | Medium |
| [IMP-002](selected/IMP-002.md) | Workspace mechanics + round/cadence semantics | Proposed | High |
| [IMP-003](selected/IMP-003.md) | Equivocality heuristic (message vs workspace) | Proposed | Medium |
| [IMP-004](selected/IMP-004.md) | The `introduce` mechanism | Proposed | Medium |
| [IMP-005](selected/IMP-005.md) | Mechanize verification (gap G1) | Proposed | High |
| [IMP-006](selected/IMP-006.md) | Maintain decision log + traceability map as living registers | Proposed | Medium |
| [IMP-016](selected/IMP-016.md) | Refactor `product-breakdown` nodes to the AD-009 budget | Completed | Medium |

Other open candidates are listed in the [roadmap.md](roadmap.md) register (IMP-008…IMP-015); selected ones are filed under `selected/`.

## Owns
- Roadmap, risks, improvement candidates (IMPs), deferred work

## Excludes
- Current definition, current baseline → `00-intent/`, `01-product/`
- Decision records → the owning layer's `decisions/` (there is no `ED-*` class)
- Runbook → `05-operation/`
- Existing-evidence claims → `04-verification/`

## Contents

<!-- pb:index:start -->
- **INFO-139** [Undeveloped suggestions — superseded](__undeveloped_sugestions__.md) — This file is the pre-move original of the raw suggestion log. It is superseded by , the canonical log (same items, updated paths, and DONE/RESOLVED/PI…
- **INFO-140** [Backlog — raw suggestion log](backlog.md) — Raw idea/suggestion log for the evolution layer (moved from ). Disposition markers: DONE / RESOLVED / PICKED UP (with target); unmarked items are open…
- **INFO-196** [Roadmap — dynamic_harness](roadmap.md) — IMP-style register of open work. Created 2026-09-21 (fills review GAP-4 — the repo previously had no roadmap; the suggestions file pointed at , a path…
- [Investigations](investigations/README.md) — Design-space investigations feeding the roadmap register
- [Selected IMPs](selected/README.md) — Filed improvement records. An IMP is a scoped candidate needing a task contract — not implementation approval. The roadmap is the full register (IMP-0…
<!-- pb:index:end -->

## Rules

- Assign the next free IMP number; prefer updating an existing IMP's status over creating competing records.
- Cross-list every IMP here with its stage; status is read from the file header.
- The roadmap is the canonical answer to "what is decided vs proposed vs abandoned" — future runs must not re-search the same design space.