# Change Pipeline

How future changes are worked before they are implemented.

## The Pipeline

```
Idea → IMP (Proposed) → IMP (Selected, scoped) → decision record in the
       owning layer (if baseline-changing or cross-layer) → owning layer
       adopts → task contract → implement → verify → IMP removed
```

An IMP is a **scoped candidate**, not implementation approval. A change is
implementable only once it has a task contract (Objective / Scope / Acceptance)
and — if it alters an accepted baseline or spans layers — an accepted decision
record that the owning layer cites as authority.

## Choosing IMP vs Decision Record vs Task

- **IMP** — any improvement candidate with an evidence-backed pain/risk that is
  not yet decided. Creating an IMP requires no permission and confers no approval.
- **Decision record** — a change that (a) modifies an accepted owning-layer
  baseline, (b) spans more than one layer, or (c) supersedes an existing
  decision. Filed under the owning layer's `decisions/` with that layer's prefix
  (`ID`/`PD`/`AD`/`IMD`/`VD`/`OD`), follows the ADR template, and is logged.
- **Task** — concrete work derived from an accepted IMP/decision record, with
  explicit scope and acceptance. Only tasks produce code changes.

Rule of thumb: if the change is already decided and only the doing is left, it is
a task, not a new record. Prefer updating an existing IMP/record over creating a
new number.

## IMP Lifecycle

- Lifecycle: `Proposed → Selected`, then the candidate is **removed** once its
  resulting state is written into the owning layer. Status is read **only** from
  the IMP file header; never maintain a second status copy.
- Every IMP is cross-listed in `06-evolution/README.md`. A listed IMP must have a
  real file; do not list phantom IDs.
- Update an IMP's status in place; do not create competing records for the same
  candidate.

## Graduating to Implementation

A change may be implemented only when all hold:

1. Owning layer cites the accepted decision record (or an adopted IMP) as authority.
2. Task contract has Objective / Scope / Acceptance.
3. Verification/acceptance criteria are defined.
4. The resulting state is written into the owning layer in the same change, and
   the registers are updated.
