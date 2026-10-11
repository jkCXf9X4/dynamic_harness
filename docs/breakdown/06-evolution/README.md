---
title: Layer 06 — Evolution
summary: What controlled changes come next?
---

# Layer 06 — Evolution

**What controlled changes come next?**

The evolution layer is the controlled-change register: the roadmap (INFO-196) is the canonical list of open work — each item with status, priority, evidence, and a task-contract seed — and `backlog.md` (INFO-140) is the raw idea/suggestion log. Selected IMPs are filed under `selected/` and cross-listed in the generated Contents below. An IMP is **a scoped candidate needing a task contract before code changes — not implementation approval.**

## IMP lifecycle

- Stages: Proposed to Selected to Implemented.
- Status is read only from the IMP file header (front-matter `status:`); no second copy.
- Implemented IMPs move to `implemented/` and are no longer tracked (IMP-016 is the exemplar).

## Owns
- Roadmap, risks, improvement candidates (IMPs), deferred work

## Excludes
- Current definition, current baseline → `00-intent/`, `01-product/`
- Decision records → the decision archive (`docs/archive/archive.zip`; there is no `ED-*` class)
- Runbook → `05-operation/`
- Existing-evidence claims → `04-verification/`

## Contents

<!-- pb:index:start -->
<!-- GENERATED FILE — do not edit. Regenerate with pb-registers. -->
- **INFO-140** [Backlog — raw suggestion log](backlog.md) — Raw idea/suggestion log for the evolution layer. Disposition markers: DONE / RESOLVED / PICKED UP (with target); unmarked items are open.
- **INFO-196** [Roadmap — dynamic_harness](roadmap.md) — IMP-style register of open work. Created 2026-09-21 (fills review GAP-4); replaces the stale docs/roadmap/LIVE_CAPITAL_READINESS.md pointer that never existed.
- [Implemented IMPs](implemented/README.md) — Implemented improvement candidates — historical; no longer tracked.
- [Investigations](investigations/README.md) — Design-space investigations feeding the roadmap register
- [Selected IMPs](selected/README.md) — Filed IMP records (IMP-001..006). An IMP is a scoped candidate needing a task contract — not implementation approval.
<!-- pb:index:end -->

## Rules

- Assign the next free IMP number; prefer updating an existing IMP's status over creating competing records.
- Cross-list every open IMP in the generated Contents; status is read from the file header.
- The roadmap is the canonical answer to "what is decided vs proposed vs abandoned" — future runs must not re-search the same design space.
