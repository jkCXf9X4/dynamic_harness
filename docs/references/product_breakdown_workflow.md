---
name: product-breakdown-workflow
description: Executable operating rules for working inside an established product-breakdown/ structure — canonical storage, the IMP→ED→task change pipeline, traceability (decision log + traceability map), and the edit checklist. Read when editing a repo's layer READMEs, decision records, IMPs, or registers. Complements the product-breakdown skill (structure + templates).
---

# Working Guidelines for the Product Breakdown Structure

Operating rules for (a) how information is stored in `product-breakdown/` and
(b) how future changes are worked before they are implemented, with traceability
kept unbroken. The layer ownership and boundary rules in the repo's own
`product-breakdown/README.md` are authoritative; this document makes them
executable for day-to-day and agent-driven edits.

> **Relationship to the skill.** `docs/references/product_breakdown_skill.md`
> describes the *structure* — the seven layers, decision-record prefixes, and the
> ADR/IMP templates. This document is the *operating workflow* for a repo that has
> already stood up that structure. Each repo owns its exact layout; where this
> document and a repo's `product-breakdown/README.md` disagree, the repo's
> README wins.

## 1. How information is stored

### 1.1 Canonical state, never accumulation

- Each fact has exactly one home. When a fact changes, **update, replace, or
  supersede** the existing representation; never append a second truth beside it.
- The layer README holds the **current state**; a decision record holds the
  **rationale** for how the state got that way; Evolution holds **candidates**
  for change. Do not re-describe current state in Evolution, and do not store
  rationale inside a layer README.
- Information flows downward only (Intent → Product → Architecture →
  Implementation → Verification → Operation). Do not push design detail up.

### 1.2 Ownership and the boundary rule

- Route every addition through the boundary rule in the repo's
  `product-breakdown/README.md`: reason-to-exist → Intent; promised deliverable →
  Product; organizing design → Architecture; files/scripts/interfaces/configs →
  Implementation; proof/acceptance → Verification; routine build/release →
  Operation; future work or risk → Evolution.
- For cross-layer material, keep the canonical statement at the layer owning the
  primary concern and defer the secondary concern by reference; state carve-outs
  explicitly at the owning layer.

### 1.3 Proportionality

- Records are small, decisive, canonical. Do not copy rationale that already
  lives in a layer README, a variant doc, or a decision record.

### 1.4 Routing table — where each type of information lives

| Type of information | Home |
|---|---|
| Current scope / state / requirements / interfaces | owning layer README |
| Decided rationale (why the baseline is what it is) | `<layer>/decisions/<PREFIX>-NNN-<slug>.md` |
| Candidate / future change (not yet decided) | `06-evolution/` as an IMP |
| Accepted cross-cutting change decision | `06-evolution/decisions/ED-NNN-<slug>.md` |
| Registry of all decisions | `decision-log.md` (one row per ADR/IMP) |
| Claim/Need → Decision → Artifact links | `traceability-map.md` |
| Raw, unresolved notes | `06-evolution/undeveloped_suggestions.md` — only until resolved, then removed or superseded |

## 2. Working with future changes before they are implemented

### 2.1 The change pipeline

```
Idea → IMP (Proposed) → IMP (Selected, scoped) → ED (if baseline-changing
       or cross-layer) → owning layer adopts → task contract → implement
       → verify → IMP Completed
```

An IMP is a **scoped candidate**, not implementation approval. A change is
implementable only once it has a task contract (Objective / Scope / Acceptance)
and — if it alters an accepted baseline or spans layers — an accepted ED that the
owning layer cites as authority.

### 2.2 Choosing IMP vs ED vs task

- **IMP** — any improvement candidate with an evidence-backed pain/risk that is
  not yet decided. Creating an IMP requires no permission and confers no approval.
- **ED** — a change that (a) modifies an accepted owning-layer baseline, (b)
  spans more than one layer, or (c) supersedes an existing decision. An ED must
  follow the ADR template and be logged.
- **Task** — concrete work derived from an accepted IMP/ED, with explicit scope
  and acceptance. Only tasks produce code changes.

Rule of thumb: if the change is already decided and only the doing is left, it is
a task, not a new record. Prefer updating an existing IMP/ED over creating a new
number.

### 2.3 IMP lifecycle rules

- Lifecycle: `Proposed → Selected → Completed` (or `Superseded`). Status is read
  **only** from the IMP file header; never maintain a second status copy.
- Every IMP is cross-listed in `06-evolution/README.md` (Implementation Status
  table). A listed IMP must have a real file; do not list phantom IDs.
- Update an IMP's status in place; do not create competing records for the same
  candidate.

### 2.4 Graduating to implementation

A change may be implemented only when all of these hold:

1. Owning layer cites the accepted ED (or an adopted IMP) as authority.
2. Task contract has Objective / Scope / Acceptance.
3. Verification/acceptance criteria are defined (Verification owns the proof).
4. The resulting state is written into the owning layer README in the same
   change, and registers are updated (see §3.5).

## 3. Traceability

### 3.1 The traceability chain

`Claim or Need → Decision Record(s) → Artifact(s)` is maintained in
`traceability-map.md`. The decision log (`decision-log.md`) is the registry of
every decision; the map is the index from need to evidence.

### 3.2 Forward traceability (need → decision → artifact)

- Every new or edited decision record MUST get a row in `decision-log.md`
  (ID, title, status, layer, location, supersedes/superseded-by).
- Every decision record MUST list **Affected Artifacts** with concrete
  repo-relative paths (e.g. `src/.../module.py`). No layer is exempt — a decision
  without artifact linkage is untraceable.
- When a decision changes which artifacts it affects, re-point the affected rows
  in `traceability-map.md` in the same change.

### 3.3 Reverse traceability (artifact → decision)

- The map is the index; reverse lookups resolve through each record's Affected
  Artifacts paths.
- A decision that builds on or refines another must name it (e.g. "Parent
  decisions: ED-003, ED-004"). This is how change decisions in Evolution point
  back to the layer decisions they amend.

### 3.4 Supersession protocol

- Supersession is **binary and bidirectional**: set `Supersedes` on the new
  record and `Superseded By` on the old record, and update the log for both.
- Partial supersession must be stated explicitly in both records (e.g.
  "Partially supersedes PD-003") and must never leave a dangling pointer to a
  nonexistent IMP or ADR.
- Superseded records remain as historical rationale but are clearly marked; the
  current truth moves to the superseding record, which owns the updated state.

### 3.5 Keeping the chain unbroken

- Registers must match real files: no decision-log row without a file, no IMP
  listed without a file, no traceability-map reference to a missing artifact.
- Editing any layer README, decision record, or IMP requires checking
  `decision-log.md` and `traceability-map.md` in the same change.
- If an artifact path changes, update the map — do not leave the old path.

## 4. Edit checklist (for humans and agents)

Before writing: locate the canonical home (§1.4), check for an existing
representation, and decide create / update / merge / supersede / remove.

After editing: confirm the decision log and traceability map are consistent with
the files touched; run the repo's own build command (e.g. `./build.sh`, per its
`05-operation/` runbook) for LaTeX edits and the repo's test command (e.g.
`python3 -m pytest`) for scaffold edits.
