# Product Breakdown Structure

Planning material for the paper, kept as a seven-layer product-definition flow
with per-layer decision records, an improvement-candidate register, and two
cross-cutting registers. The layer boundary rule and node rules below are
authoritative; day-to-day operating rules live in
[`WORKING-GUIDELINES.md`](WORKING-GUIDELINES.md).

Working title: **System Architecture and Co-Simulation Algorithm Choices
Matter: A Comparative FMI/SSP Study of Coupled Simulation Breakup Strategies**.

Core thesis: for coupled simulation systems, architecture and scheduling are not
neutral. A model that is mathematically identical at the monolithic-system level
can produce different results when decomposed into different FMU structures and
executed with different co-simulation algorithms.

## Node Model (AD-009)

Every markdown file here is a **node** with a size budget:

- **Index node** (one per folder/layer, `README.md`): target ≤40 lines, hard
  cap 75; purpose, owns/excludes, a `link → one-line description` table,
  decisions pointer. No rationale or substantive detail.
- **Leaf node**: one concern; target ≤50 lines, hard cap 75, minimum ~10 lines
  of unique content.

Over cap → **trim**, then **link**, then **split** along a concern seam. Keep
exactly one canonical leaf per fact. Never split a decision record. Naming is by
role; folder indexes are `README.md`.

## Layers

Read in order from idea to maintained artifact. Each layer answers one primary
question and must not duplicate ownership from adjacent layers.

| Layer | Question | Owns | Excludes |
|---|---|---|---|
| [Intent](00-intent/README.md) | Why does the paper exist, who is it for? | Motivation, stakeholders, research questions, outcomes, constraints, assumptions | Deliverables, design, scripts, tests, release, backlog |
| [Product](01-product/README.md) | What is delivered, out of scope? | Scope, capabilities, use cases, requirements, glossary, acceptance expectations | Paper organization, implementation, test mechanics, runbooks, roadmap |
| [Architecture](02-architecture/README.md) | How are paper, evidence, experiments organized? | Manuscript structure, study structure, components, data flow, integration, quality attributes | Script interfaces, file notes, test cases, release steps |
| [Implementation](03-implementation/README.md) | With what assets is it realized? | Repo layout, build modules, experiment scripts, model resources, interfaces, config conventions | Scope, architecture rationale, proof criteria, release policy, future features |
| [Verification](04-verification/README.md) | How do we know it satisfies requirements? | Acceptance criteria, test strategy, test cases, traceability, numerical checks, reproducibility | New requirements, architecture changes, routine run commands, future work |
| [Operation](05-operation/README.md) | How do authors run, maintain, release? | Runbook, build/test/release workflow, monitoring, release practice | Design rationale, internals, verification criteria, backlog |
| [Evolution](06-evolution/README.md) | What controlled changes come next? | Roadmap, risks, improvement candidates (IMPs), deferred work | Current baseline, runbook, existing-evidence claims, accepted change decisions |

**Boundary rule:** reason-to-exist → Intent; promised deliverable → Product;
organizing design → Architecture; files/scripts/interfaces/configs →
Implementation; proof/acceptance → Verification; routine build/release →
Operation; future work or risk → Evolution. For cross-layer material keep the
canonical statement at the layer owning the primary concern and defer the
secondary concern by reference.

Decisions that change the baseline live in the owning layer's `decisions/` with
that layer's prefix (`ID`/`PD`/`AD`/`IMD`/`VD`/`OD`); Evolution holds only
unimplemented candidates, roadmap, and risks. Interfaces are contracts:
Implementation states what commands/arguments exist, Operation states which
authors run and when.

## Registers

- [`decision-log.md`](decision-log.md) — one row per decision, kept current.
- [`traceability-map.md`](traceability-map.md) — Claim/Need → Decision(s) →
  Artifact(s); update when a claim, decision, or artifact changes.

Decision records use [`ADR-template.md`](ADR-template.md) exactly, are kept
small and decisive (≤~50 lines), and must be reflected in the decision log.
Supersession is binary and bidirectional. Registers are cross-cutting: editing
any node may require updating them in the same change.
