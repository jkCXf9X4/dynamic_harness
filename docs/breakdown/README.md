---
title: Product Breakdown — dynamic_harness
summary: Seven-layer definition state of the repo — current state, boundary rule, node model, registers.
---

# Product Breakdown — dynamic_harness

The repo's **definition state**: the seven-layer breakdown that makes the development rationale explicit. Binding instance of the [`product-breakdown` method](../../3rd_party/agent_methods_and_tools/src/agent_methods/methods/product-breakdown/SKILL.md) (installed as a skill into `.agents/skills/`). Every leaf carries a stable content-type id (`INFO-`/`EVAL-`/`IMP-`) cited in backticks; decisions and retired material are cold-stored in the decision archive; layer indexes and the archive index are generated.

## The Seven Layers

Read top-down. Each layer answers one question and must NOT duplicate ownership from adjacent layers. A document's home is the layer whose question it answers; information flows downward only, design detail never pushed up.

| Layer | Question | Contents |
|---|---|---|
| `00-intent/` | Why does the project exist, who is it for? | VISION.md, competitive-differentiation/ |
| `01-product/` | What is delivered, out of scope? | requirements/, use-cases/ |
| `02-architecture/` | How are deliverables, evidence, and work organized? | methodology/, concepts/, examples/ |
| `03-implementation/` | With what concrete assets is it realized? | index only; assets stay at repo root |
| `04-verification/` | How do we know it satisfies requirements? | gap-analysis/ (G1–G13) |
| `05-operation/` | How do authors run, maintain, release? | runbook/, guides/ |
| `06-evolution/` | What controlled changes come next? | roadmap.md, backlog.md, selected/, implemented/, investigations/ |

## Node Model

- Every markdown file is a **node** with a size budget (`AD-009`), enforced by `pb node-size --strict`.
- **Index** — one per folder, `README.md`. Navigational only: purpose, owns/excludes, generated `## Contents`, decisions pointer. Goal ≤40, warn 50, hard cap 75.
- **Leaf** — one concern. Goal ≤50, warn 75, hard cap 100, minimum ~10. Decision records are never split — tighten or supersede. Over cap: **trim**, then **link**, then **split** along a concern seam; one canonical leaf per fact. The leaf's `summary` is the generated `## Contents` row.
- Long reference material may exempt itself with `pb_exempt: true` (five investigation docs under `06-evolution/investigations/`).

## Registers

- **Decision archive** (`../archive/archive.zip`) — cold-stores every committed choice and retired material. History is reached only via `pb archive list` / `pb archive read <ID>` — never browsed, globbed, or unzipped. The generated index (`../archive/README.md`) is the only loose surface.
- **Decision log** (`../archive/design-choice-log.md`) — generated from record front-matter, newest first; replaces the hand-written `decision-log.md` (retired to the archive's `deprecated/`).
- **Traceability map** (`traceability-map.md`) — hand-written. Claim/Need → Decision Record(s) → Artifact(s); closes the V-model loop. Covers claims and needs, not only records.

## Decision Records & IMPs

- **Records** live at the archive zip root as `<PREFIX>-<NNN>-<slug>.md`, added via `pb archive add`, read via `pb archive read <ID>`; shape per the method skill's `templates/TEMPLATE.md`. Leaf id prefix is **type-driven** (`info`→`INFO-`, `eval`→`EVAL-`, `imp`→`IMP-`); per-layer prefixes (ID/PD/AD/IMD/VD/OD) are grandfathered for **decision records only**. Status ∈ `proposed | accepted | superseded | rejected | deprecated`.
- **IMPs** live under `06-evolution/selected/IMP-NNN.md` — a scoped candidate needing a task contract, **not** implementation approval. Implemented IMPs move to `06-evolution/implemented/` and are no longer tracked. New/edited IMPs are cross-listed in `06-evolution/README.md` with stage.

## Browsing (for agents)

State, history, candidates, and tracking are separate surfaces; a read must not mix them. Current-state question: read the layer index, then the one leaf owning the concern, stop when the fact is found. Archive, IMPs, `investigations/` only for *why / what's next*, never *what is*. Never whole-directory read `selected/` or `investigations/` — `grep` scoped to the owning layer. `superseded`/`deprecated` is a redirect or tombstone, not evidence. Full protocol: the method skill's `guidelines/browsing-protocol.md`.

## Maintenance

- New records: `pb archive add <file>` (retired material: `--deprecated`); the command deletes the loose file. Update `traceability-map.md` when a claim, decision, or artifact changes.
- After editing a node: `pb check --strict` + `pb node-size --strict` from this directory (or the repo root); resolve violations (trim → link → split). Writing a node: apply the method's `guidelines/readability-rules.md`; where repo rules conflict, repo rules win.
- Registers and `## Contents` lists are generated — `pb registers` regenerates; never hand-edit (banner marks it). `pb registers --clear` strips every generated surface between releases.
