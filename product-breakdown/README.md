# Product Breakdown — dynamic_harness

This directory is the repo's **definition state**: the seven-layer product breakdown that makes the development rationale explicit. It is the binding instance of the convention defined in [`docs/references/product_breakdown_skill.md`](../docs/references/product_breakdown_skill.md). Every document that answers one of the seven layer questions lives in its layer; every durable decision is recorded (ADR record + decision log); every claim/need is traced to the decision(s) and artifact(s) that realize it; every piece of future work is registered in the evolution layer. Created 2026-09-21 as the instantiation of that convention (see `.dynamic-harness/260921_153611_b5cb/artifacts/breakdown_structure_critical_review.md`), wrapping — not replacing — the existing INVESTIGATION→PLAN→FINDINGS→RESULTS rationale that already lives in the moved files.

## The Seven Layers

Read top-down. Each layer answers one primary question and must NOT duplicate ownership from adjacent layers.

| Layer | Question | Contents (post-move) |
|---|---|---|
| `00-intent/` | Why does the project exist, who is it for? | VISION.md, competitive-differentiation.md, platform-evaluation.md |
| `01-product/` | What is delivered, out of scope? | requirements.md (CLI sub-spec), use-cases/ |
| `02-architecture/` | How are deliverables, evidence, and work organized? | agent_methodology_guidelines.md, concepts/, examples/, decisions/ (ADRs), multi-agent-coordination/ |
| `03-implementation/` | With what concrete assets is it realized? | plugin/; src/, prompts/, resources/, scripts/, pyproject.toml, harness.json.example stay in place |
| `04-verification/` | How do we know it satisfies requirements? | gap-analysis.md, communication-structures/ |
| `05-operation/` | How do authors run, maintain, release? | runbook.md, guides/ |
| `06-evolution/` | What controlled changes come next? | roadmap.md, backlog.md, selected/ (IMPs) |

## Boundary Rule

Text that changes the reason-to-exist → **Intent**; the promised deliverable → **Product**; the organizing design → **Architecture**; files/scripts/interfaces/configs → **Implementation**; proof/acceptance checks → **Verification**; how authors build/release → **Operation**; future work or risk → **Evolution**.

A document's home is the layer whose primary question it answers. Information flows downward only (Intent → Product → Architecture → Implementation → Verification → Operation); design detail is never pushed up into higher layers.

## Node Model

Every markdown file here is a **node** with a size budget ([AD-009](02-architecture/decisions/AD-009.md)), enforced by `tools/check_node_size.py --strict`.

- **Index node** — one per folder, `README.md`. Navigational only: purpose, owns/excludes, a `link → one-line description` table, decisions pointer. No rationale or substantive detail. Target ≤40 lines, hard cap 75.
- **Leaf node** — one concern; target ≤50 lines, hard cap 75, minimum ~10. Decision records stay ≤~50 and are never split — tighten or supersede.
- Over cap → **trim**, then **link**, then **split** along a concern seam. Keep exactly one canonical leaf per fact. Name files by role; folder indexes are `README.md`.
- Existing oversized nodes are grandfathered in `tools/node_size_allowlist.txt` and refactored under IMP-016; `--strict` is clean once that list is empty.

## Cross-Cutting Registers

- **[Decision log](decision-log.md)** — one row per decision (DL-1…DL-15); kept current whenever an ADR is added, edited, or superseded.
- **[Traceability map](traceability-map.md)** — Claim/Need → Decision Record(s) → Artifact(s); closes the V-model loop at repo level ("every output traced to a requirement").

## Decision Records & IMPs

- **ADRs** live under `02-architecture/decisions/<PREFIX>-<NNN>-<slug>.md`, per [`docs/references/templates/ADR-template.md`](../docs/references/templates/ADR-template.md). Prefixes map to layers: ID/PD/AD/IMD/VD/OD/ED. Status ∈ `Proposed | Accepted | Superseded | Rejected | Deprecated`. Created in a parallel track (AD-001…).
- **IMPs** live under `06-evolution/selected/IMP-NNN.md`, per [`docs/references/templates/IMP-template.md`](../docs/references/templates/IMP-template.md) — a scoped candidate needing a task contract, **not** implementation approval. Cross-listed in `06-evolution/README.md`.

## What Stays Runtime-Coupled in docs/

`docs/api/` (module API reference) and `docs/references/` (skill, templates, durable rationale docs) remain in `docs/` — they are runtime-coupled. `docs/README.md` explains the split.

## Maintenance

- Every new/edited ADR MUST be reflected in `decision-log.md` (ID, title, status, layer, location, supersedes/superseded-by); update `traceability-map.md` when a claim, decision, or artifact changes.
- After editing any node, run `python3 product-breakdown/tools/check_node_size.py --strict` and resolve violations (trim → link → split).
- Every new/edited IMP is cross-listed in `06-evolution/README.md` with its stage.
- Follow the skill's layer hygiene and the repo's own information-hygiene rule (canonical state, no duplication). Where the repo's rules conflict with the pattern, the repo's rules win.