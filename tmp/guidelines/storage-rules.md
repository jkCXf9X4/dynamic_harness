# Storage Rules

How information is stored in `product-breakdown/`.

## Canonical State, Never Accumulation

- Each fact has exactly one home. When a fact changes, **update, replace, or
  supersede** the existing representation; never append a second truth beside it.
- The layer README/index holds the **current state**; a decision record holds the
  **rationale**; Evolution holds **candidates** for change. Do not re-describe
  current state in Evolution, and do not store rationale inside an index.
- Information flows downward only (Intent → Product → Architecture →
  Implementation → Verification → Operation). Do not push design detail up.

## Ownership and the Boundary Rule

- Route every addition through the boundary rule in
  [`../README.md`](../README.md): reason-to-exist → Intent; promised deliverable
  → Product; organizing design → Architecture; files/scripts/interfaces/configs
  → Implementation; proof/acceptance → Verification; routine build/release →
  Operation; future work or risk → Evolution.
- For cross-layer material, keep the canonical statement at the layer owning the
  primary concern and defer the secondary concern by reference; state carve-outs
  explicitly at the owning layer.

## Node Budget (AD-009)

- **Index node** (one per folder/layer, `README.md`): target ≤40 lines, hard
  cap 75; purpose, owns/excludes, a `link → one-line description` table,
  decisions pointer. No rationale or substantive detail.
- **Leaf node**: one concern; target ≤50 lines, hard cap 75, minimum ~10 lines
  of unique content.
- Over cap → **trim** material owned elsewhere, **link** instead of repeat, then
  **split** along a concern seam. Keep exactly one canonical leaf per fact.
- Never split a decision record; tighten it or supersede it.
- Name files by role; folder indexes are `README.md`.

## Routing Table

| Type of information | Home |
|---|---|
| Current scope / state / requirements / interfaces | owning layer index + leaves |
| Decided rationale / accepted change decision | the owning layer's `decisions/<PREFIX>-NNN-<slug>.md` |
| Candidate / future change (not yet decided) | `06-evolution/selected/` as an IMP |
| Registry of all decisions | `../decision-log.md` |
| Claim/Need → Decision → Artifact links | `../traceability-map.md` |
