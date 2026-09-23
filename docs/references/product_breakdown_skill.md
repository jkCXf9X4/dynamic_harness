---
name: product-breakdown
description: Use when a task involves a repo's product-breakdown structure — ADR-style decision records, IMP candidates, the decision log, the traceability map, or the seven layer READMEs. Not for ordinary edits.
---

# Product Breakdown Structure

A reusable systems-engineering structure for keeping a project's definition
state in `product-breakdown/`: a seven-layer product-definition flow, per-layer
decision records, an implementation-candidate register (IMPs), and two
cross-cutting registers (decision log, traceability map). A repo that follows
this structure owns its exact layout in `product-breakdown/README.md`; the
layer boundary rule lives there.

## The Seven Layers

Read them in order from idea to maintained artifact. Each answers one primary
question and must NOT duplicate ownership from adjacent layers.

| Layer | Question | Owns | Excludes |
|---|---|---|---|
| `00-intent/` | Why does the project exist, who is it for? | Motivation, stakeholders, research questions, outcomes, constraints, assumptions | Deliverables, design, scripts, tests, release, backlog |
| `01-product/` | What is delivered, out of scope? | Scope, capabilities, use cases, requirements, glossary, acceptance expectations | Organization, implementation, test mechanics, runbooks, roadmap |
| `02-architecture/` | How are deliverables, evidence, and work organized? | Structure, components, data flow, integration, quality attributes | Script interfaces, file notes, test cases, release steps |
| `03-implementation/` | With what concrete assets is it realized? | Repo layout, build modules, scripts, model resources, interfaces, config conventions | Scope, architecture rationale, proof criteria, release policy, future features |
| `04-verification/` | How do we know it satisfies requirements? | Acceptance criteria, test strategy, test cases, traceability, numerical checks, reproducibility | New requirements, architecture changes, routine run commands, future work |
| `05-operation/` | How do authors run, maintain, release? | Runbook, build/test/release workflow, monitoring, release practice | Design rationale, internals, verification criteria, backlog |
| `06-evolution/` | What controlled changes come next? | Roadmap, risks, improvement candidates (IMPs), deferred work | Current definition, current baseline, runbook, existing-evidence claims, decision records |

**Boundary rule:** text that changes the reason-to-exist → Intent; the promised
deliverable → Product; the organizing design → Architecture; files/scripts/
interfaces/configs → Implementation; proof/acceptance checks → Verification;
how authors build/release → Operation; future work or risk → Evolution.

## Decision Records (ADRs)

One file per decision under `<layer>/decisions/<PREFIX>-<NNN>-<slug>.md`.
Prefixes map to layers: `ID`=Intent, `PD`=Product, `AD`=Architecture,
`IMD`=Implementation, `VD`=Verification, `OD`=Operation. 

There is no `ED-*` class: a decision is homed at — and honored by — the layer that owns its resulting state. Evolution holds only roadmap, risks, and unimplemented IMP
candidates.

Use the structure's ADR template
(`docs/references/templates/ADR-template.md`) exactly. Required sections:
Status, Layer, Context, Decision, Alternatives Considered, Consequences,
Affected Artifacts, Verification, Review Trigger, Supersedes, Superseded By.

Rules:
- Status is one of `Proposed | Accepted | Superseded | Rejected | Deprecated`.
- Every new/edited record MUST be reflected in the decision log (ID, title,
  status, layer, location, supersedes/superseded-by).
- When superseding, set `Supersedes` on the new record and `Superseded By` on
  the old record; update the decision log for both. The traceability map may
  need the superseded record's artifact entries re-pointed.
- Keep records proportional: decisions are small, decisive, canonical. Do not
  copy rationale that already lives in a layer README or a variant doc.

## Implementation Candidates (IMPs)

Future/selected work lives under `06-evolution/`. Selected IMPs are filed at
`06-evolution/selected/IMP-NNN.md`; status is read from the file header.
Lifecycle: `Proposed → Selected → removed once implemented` (or `Superseded`).

An implemented IMP is removed — its resulting state lives in the owning layer's
README and decision record, not in Evolution.

The IMP template (`docs/references/templates/IMP-template.md`) includes:
Lifecycle Stage, Status, Layer, Theme, Evidence, Current Pain Or Risk, Proposed
Improvement, Risk And Blast Radius, Dependencies, Suggested Priority, Selected
Date, Task Contract Seed (Objective/Scope/Acceptance), Out Of Scope, Traceability.

Rules:
- An IMP is not implementation approval. It is a scoped candidate needing a
  task contract before code changes.
- Cross-list every IMP in `06-evolution/README.md` (Implementation Status
  table) with its stage.
- Prefer updating an existing IMP's status over creating competing records.
- Assign the next free IMP number.

## Registers

- Decision log — accepted decisions affecting more than one section. One row
  per decision; kept current.
- Traceability map — links Claim/Need → Decision Record(s) → Artifact(s).
  Update when a claim, decision, or artifact changes.

## Ground Rules

A repo may keep binding, cross-cutting ground rules in a dedicated README
(e.g. `01-product/variants/README.md`). These are axiom-like constraints decided
in ADRs and owned in exactly one place; per-document content must not re-encode
them. Examples of the shape, drawn from one deployment:

1. Independent concerns are never folded into one document — each stays
   axis-pure and delegates cross-cutting behavior to a compatibility matrix.
2. A shared strategy set is defined once; per-study realization happens per
   study, never by copying the shared document.
3. Combination status is decided once in the compatibility matrix — axis docs
   must not encode it.
4. A reference implementation is the oracle for correctness.
5. Canonical state, not accumulation — a variant's status, keys, and rationale
   live in exactly one place; updates replace the owning document.

Ground rules of a specific repo are authoritative for that repo; where they
conflict with this pattern, the repo's own rules win.

## Node Model

Every markdown file in the structure is a **node**, and each node has a size
budget. The point is retrieval: a reader must be able to tell on sight what is
navigational, what is one concern, and what is authoritative.

- **Index node** — one per folder, `README.md`. Navigational only: purpose,
  owns/excludes, a `link → one-line description` table, a decisions pointer. No
  rationale or substantive detail.
- **Leaf node** — one concern. Exactly one canonical leaf per fact.
- **Over cap → trim → link → split**: first trim material owned elsewhere, then
  replace repetition with a link, then split along a concern seam. Never split a
  decision record — tighten or supersede it.
- Name files by role; folder indexes are always `README.md`.

The budget is **repo-declared** — a repo sets its own limits in
`product-breakdown/README.md` (a common shape: index target ≤40 / hard cap 75,
leaf target ≤50 / hard cap 75, minimum ~10). A repo may enforce it with a
checker (e.g. `product-breakdown/tools/check_node_size.py --strict`). When
adopting the budget while many nodes are still overweight, phase the refactor
behind a **temporary** allow-list that is emptied and removed once the checker
is clean — never leave it as a permanent exemption.

The budget bounds a node's *size*; the **readability rules** — one fact per
line, scannable structure, plain language, proportional-never-padded — keep it
easy to read and are the operating counterpart, owned in
`product_breakdown_workflow.md` §1.5.

## Layer Hygiene

- Follow the library's information-hygiene doc
  (`docs/references/information_hygiene.md`): canonical state, no duplication,
  remove or supersede stale information.
- Information flows downward only (Intent → Product → Architecture →
  Implementation → Verification → Operation). Do not push design detail up
  into higher layers.

## Verification

After editing decision records, IMPs, layer READMEs, or registers:
- Re-check that the decision log and traceability map are consistent with the
  files you touched.
- For substantive edits, run the repo's own build/test commands (see its
  `05-operation/` runbook) and confirm they pass.