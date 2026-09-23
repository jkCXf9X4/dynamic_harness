# Traceability Rules

Keeping `Claim or Need → Decision Record(s) → Artifact(s)` unbroken.

## The Chain

The chain is maintained in [`../traceability-map.md`](../traceability-map.md).
The [decision log](../decision-log.md) is the registry of every decision; the map
is the index from need to evidence.

## Forward Traceability (need → decision → artifact)

- Every new or edited decision record MUST get a row in `decision-log.md`
  (ID, title, status, layer, location, supersedes/superseded-by).
- Every decision record MUST list **Affected Artifacts** with concrete
  repo-relative paths. No layer is exempt.
- When a decision changes which artifacts it affects, re-point the affected rows
  in `traceability-map.md` in the same change.
- If a canonical artifact is renamed or split, update every reference in the same
  change; do not leave a stale path.

## Reverse Traceability (artifact → decision)

- The map is the index; reverse lookups resolve through each record's Affected
  Artifacts paths.
- A decision that builds on or refines another must name it (e.g. "Parent
  decisions: PD-009, IMD-005").

## Supersession Protocol

- Supersession is **binary and bidirectional**: set `Supersedes` on the new
  record and `Superseded By` on the old record, and update the log for both.
- Partial supersession must be stated explicitly in both records and must never
  leave a dangling pointer to a nonexistent IMP or ADR.
- Superseded records remain as historical rationale but are clearly marked; the
  current truth moves to the superseding record.

## Keeping the Chain Unbroken

- Registers must match real files: no decision-log row without a file, no IMP
  listed without a file, no traceability-map reference to a missing artifact.
- Editing any index, decision record, or IMP requires checking `decision-log.md`
  and `traceability-map.md` in the same change.
