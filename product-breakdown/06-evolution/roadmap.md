# Roadmap — dynamic_harness

IMP-style register of open work. Created 2026-09-21 (fills review GAP-4 — the repo previously had no roadmap; the suggestions file pointed at `docs/roadmap/LIVE_CAPITAL_READINESS.md`, a path that **does not exist** — that stale pointer is replaced by this file). Status values per IMP lifecycle: `Proposed | Selected | Completed | Superseded`. Source of items: the multi-agent INVESTIGATION next-steps, the unresolved backlog items (`06-evolution/backlog.md`, moved from `breakdown/development/__undeveloped_sugestions__.md`), and the open gaps in `04-verification/gap-analysis.md`. Selected IMPs are filed at `06-evolution/selected/IMP-NNN.md` with a task contract; this register is the index.

## Register

| IMP | Theme | Status | Priority | Evidence / Source |
|-----|-------|--------|----------|-------------------|
| IMP-001 | Multi-agent: spec workspace mechanics (scoped `ArtifactStore` area + visibility + append/review conventions) | Proposed | High | INVESTIGATION next-step (the C-gap the theory does not settle); DL-7 hybrid needs a defined shared surface |
| IMP-002 | Multi-agent: round/cadence semantics (when a child fetches newly-settled siblings' writes) | Proposed | High | INVESTIGATION next-step; settle-then-yield needs reinterpretation for a shared surface |
| IMP-003 | Multi-agent: equivocality heuristic (write vs message; bias workspace-first) | Proposed | Medium | INVESTIGATION next-step; necessary for the channel rule to be non-prompt advice |
| IMP-004 | Multi-agent: `introduce` mechanism (delegation-time `collaborate_with` vs mid-run tool vs both) | Proposed | Medium | INVESTIGATION next-step; B-curated requires explicit membership (Hackman) |
| IMP-005 | Prerequisite / explicit non-goal: G1–G7 mechanism gap (mechanical verification + distinct Layer-2 heal) for coordination work | Proposed | High | INVESTIGATION next-step ("flag the G1/G7 mechanism gap as a prerequisite or explicit non-goal"); `04-verification/gap-analysis.md` G1 open (P0) |
| IMP-006 | Comms benchmark: P4 (topics_parent) churn replicates — re-measure the ~6× churn hypothesis | Proposed | Medium | `04-verification/communication-structures/FINDINGS.md` "flagged as a hypothesis… n=1"; DL-11 |
| IMP-007 | Mechanical verification of acceptance criteria (report-time gate; `verify_children=true`) | Proposed | High | `04-verification/gap-analysis.md` G1 (P0, open) — breaks "verify before synthesize" as a guarantee |
| IMP-008 | Budgeting / cost control (request-budget tool + hard token cap) | Proposed | Medium | `04-verification/gap-analysis.md` G8 (P1, open) — dead plumbing; cost is the stated #1 motivation |
| IMP-009 | Durable heal budgets across process restart | Proposed | Low | `04-verification/gap-analysis.md` G13 (P2, open) |
| IMP-010 | Agent-facing provenance / trace tool | Proposed | Low | `04-verification/gap-analysis.md` G12 (P2, open) |
| IMP-011 | USD-cost reporting in runtime/CLI | Proposed | Low | `04-verification/gap-analysis.md` G9 (P2, open) |
| IMP-012 | Docs drift cleanup (tool count 19, prompt path `core/prompts.py`, Layer-2 naming) | Proposed | Low | `04-verification/gap-analysis.md` G7/G11 |
| IMP-013 | External-benchmark scaffolding (Terminal-Bench mini / GAIA adapter as opt-in pipelines) | Proposed | Low | `../05-operation/guides/benchmark-alternatives.md` verdicts; suggestion thread "evaluate external agents / benchmarks" |
| IMP-014 | Trace send/receive for simpler debugging | Proposed | Low | `06-evolution/backlog.md` ("make the trace send and receive") |
| IMP-015 | Tight fallback loop before failing at tool-call limits (loop-point-out + recover) | Proposed | Low | `06-evolution/backlog.md` ("tighter fallback loop… point out it's looping and see if it can recover") |
| IMP-016 | Refactor `product-breakdown` nodes to the AD-009 budget (empty the size allow-list) | Selected | Medium | AD-009 / DL-17; `tools/check_node_size.py` reports 52 grandfathered nodes |

## Notes on provenance

- **IMP-001..006** migrate the multi-agent INVESTIGATION's open next-steps (all under `02-architecture/multi-agent-coordination/INVESTIGATION.md` "Investigation next steps"; completed ones are marked `[x]` there and are NOT re-registered here).
- **IMP-007..012** migrate the open gaps of `04-verification/gap-analysis.md` (G1, G7, G8, G9, G11–G13). Resolved gaps (G2–G6, G10) are NOT re-registered.
- **IMP-013..015** come from unresolved/unpicked suggestions in `06-evolution/backlog.md`.
- **IMP-016** comes from the node-model merge (AD-009): it is the refactor that empties `tools/node_size_allowlist.txt`; filed as Selected in `selected/`.
- All other statuses are **Proposed** until an IMP is written to `selected/` and Selected.

## Task-contract seed (mandatory before code changes)

Every IMP selected for work must carry a task contract before any code changes — IMP template fields: **Objective** (what "done" looks like), **Scope** (what is in scope), **Acceptance** (verifiable acceptance criteria), **Out Of Scope**, plus Evidence, Risk And Blast Radius, Dependencies, and Traceability. Selection is recorded in the IMP file header (`Lifecycle Stage: Selected`, `Selected Date`). This mirrors the repo's own rule: candidates justify themselves before implementation.

## Stale-pointer notice

`06-evolution/backlog.md` previously instructed future runs to "use docs/roadmap/LIVE_CAPITAL_READINESS.md — a to-do list for tracking… unsupervised live capital." That path never existed. **This file is the roadmap.** The live-capital readiness item (should it ever be pursued) is captured here under IMP-013's theme; no separate `docs/roadmap/` tree will be created.