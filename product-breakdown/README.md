# Product Breakdown — dynamic_harness

This directory is the repo's **definition state**: the seven-layer product breakdown that makes the development rationale explicit. It is the binding instance of the per-layer convention defined in the generic [`product-breakdown` method](../../3rd_party/agent_methods_and_tools/src/agent_methods/methods/product-breakdown/SKILL.md) (installed as a skill into `.agents/skills/`), migrated to that method's current model (2026-09-29): every leaf carries a stable content-type id (`INFO-`/`EVAL-`/`IMP-`) cited in backticks, decision records live in the flat `decisions/` stream, and layer indexes and `decisions/README.md` are generated. Every document that answers one of the seven layer questions lives in its layer; every durable decision is recorded; every claim/need is traced to the decision(s) and artifact(s) that realize it; every piece of future work is registered in the evolution layer. Created 2026-09-21 as the instantiation of that convention (see `.dynamic-harness/260921_153611_b5cb/artifacts/breakdown_structure_critical_review.md`), wrapping — not replacing — the existing INVESTIGATION→PLAN→FINDINGS→RESULTS rationale that already lives in the moved files.

## The Seven Layers

Read top-down. Each layer answers one primary question and must NOT duplicate ownership from adjacent layers.

| Layer | Question | Contents (post-move) |
|---|---|---|
| `00-intent/` | Why does the project exist, who is it for? | VISION.md, competitive-differentiation/ |
| `01-product/` | What is delivered, out of scope? | requirements/ (CLI sub-spec), use-cases/ |
| `02-architecture/` | How are deliverables, evidence, and work organized? | methodology/, concepts/, examples/ |
| `03-implementation/` | With what concrete assets is it realized? | index only; src/, prompts/, resources/, scripts/, pyproject.toml, harness.json.example stay in place at repo root |
| `04-verification/` | How do we know it satisfies requirements? | gap-analysis/ (G1–G13 register); the communication-structures evidence chain lives under `06-evolution/investigations/` |
| `05-operation/` | How do authors run, maintain, release? | runbook/, guides/ |
| `06-evolution/` | What controlled changes come next? | roadmap.md, backlog.md, selected/ (IMPs), implemented/, investigations/ |

## Boundary Rule

Text that changes the reason-to-exist → **Intent**; the promised deliverable → **Product**; the organizing design → **Architecture**; files/scripts/interfaces/configs → **Implementation**; proof/acceptance checks → **Verification**; how authors build/release → **Operation**; future work or risk → **Evolution**.

A document's home is the layer whose primary question it answers. Information flows downward only (Intent → Product → Architecture → Implementation → Verification → Operation); design detail is never pushed up into higher layers.

## Node Model

Every markdown file here is a **node** with a size budget ([AD-009](decisions/AD-009-node-model-budgeted-navigational-definition-state.md)), enforced by the method's `pb node-size --strict`.

- **Index node** — one per folder, `README.md`. Navigational only: purpose, owns/excludes, a generated `## Contents` list, decisions pointer. No rationale or substantive detail. Target ≤40 lines, hard cap 75.
- **Leaf node** — one concern; target ≤50 lines, hard cap 75, minimum ~10. Decision records are small and decisive and are never split — tighten or supersede.
- Over cap → **trim**, then **link**, then **split** along a concern seam. Keep exactly one canonical leaf per fact. Name files by role; folder indexes are `README.md`.
- Long investigation/reference material may exempt itself with `pb_exempt: true` — currently used by five investigation/proposal docs under `06-evolution/investigations/`.

## Cross-Cutting Registers

- **[Decision stream](decisions/README.md)** — generated from record front-matter: flat, dated history of every committed choice (`decisions/<PREFIX>-<NNN>-<slug>.md`).
- **[Decision log](design-choice-log.md)** — generated from record front-matter (newest-first). Replaces the hand-written `decision-log.md` (DL-1…DL-17), retired to `deprecated/` on 2026-10-02 once every row had a record or state home.
- **[Traceability map](traceability-map.md)** — Claim/Need → Decision Record(s) → Artifact(s); closes the V-model loop at repo level ("every output traced to a requirement"). Hand-written; it covers claims and needs, not only records.

## Decision Records & IMPs

- **Records** live in the flat stream under `decisions/<PREFIX>-<NNN>-<slug>.md`, following `templates/TEMPLATE.md` of the method skill (front-matter: id, title, date, status, layers, state, artifacts, supersedes, superseded_by, related; sections Context → Decision → Rationale → Alternatives Considered → Consequences → Verification → Review Trigger). Prefixes map to layers: ID/PD/AD/IMD/VD/OD; evolution candidates use IMP-. Status ∈ `proposed | accepted | superseded | rejected | deprecated`. The 9 legacy ADRs were migrated here on 2026-09-29.
- **IMPs** live under `06-evolution/selected/IMP-NNN.md` — a scoped candidate needing a task contract, **not** implementation approval. An implemented IMP moves to `06-evolution/implemented/` and is no longer tracked. Cross-listed in `06-evolution/README.md`.

## What Stays Runtime-Coupled in docs/

`docs/api/` (module API reference) and `docs/references/` (durable rationale docs) remain in `docs/` — they are runtime-coupled. Skills (task instruction packages) are installed from the generic `3rd_party/agent_methods_and_tools` library into `.agents/skills/` — also runtime-coupled. `docs/README.md` explains the split.

## Browsing (for agents)

State, history, candidates, and tracking are separate surfaces; a read must not
mix them. **For a current-state question: read state only — a layer index, then
the one leaf owning the concern — and stop when the fact is found.** Enter
`decisions/` records (via a leaf's `## Decisions` footer), IMPs, or
`investigations/` only when the question is *why / what's next*, never *what
is*. Never whole-directory read `decisions/`, `selected/`, or
`investigations/`; `grep` for a term scoped to the owning layer instead.
Anything `superseded`/`deprecated` (or under a `deprecated/` path) is a
redirect or tombstone, not evidence — follow its forward pointer or stop.
Full protocol: the method skill's `guidelines/browsing-protocol.md`.

## Maintenance

- New decision records go under `decisions/`. Update `traceability-map.md` when a claim, decision, or artifact changes.
- After editing any node, run the skill's `pb check --strict` and `pb node-size --strict` from this directory and resolve violations (trim → link → split).
- Run `pb registers --sync-footers` after record/leaf edits to regenerate `decisions/README.md`, leaf `## Decisions` footers, and index `## Contents` lists.
- Every new/edited IMP is cross-listed in `06-evolution/README.md` with its stage.
- Follow the skill's layer hygiene and the repo's own information-hygiene rule (canonical state, no duplication). When writing a node, apply the readability rules (one fact per line, scannable structure, plain language, proportional-never-padded) in the generic method's [`guidelines/readability-rules.md`](../../3rd_party/agent_methods_and_tools/src/agent_methods/methods/product-breakdown/guidelines/readability-rules.md). Where the repo's rules conflict with the pattern, the repo's rules win.

## Decisions

- AD-009 — Node Model — Budgeted, Navigational Definition State
