# Roadmap — dynamic_harness

IMP-style register of open work. Created 2026-09-21 (fills review GAP-4 — the repo previously had no roadmap; the suggestions file pointed at `docs/roadmap/LIVE_CAPITAL_READINESS.md`, a path that **does not exist** — that stale pointer is replaced by this file). Status values per IMP lifecycle: `Proposed | Selected | Completed | Superseded`. Source of items: the multi-agent INVESTIGATION next-steps, the unresolved backlog items (`06-evolution/backlog.md`, moved from `breakdown/development/__undeveloped_sugestions__.md`), and the open gaps in `04-verification/gap-analysis/README.md`. Selected IMPs are filed at `06-evolution/selected/IMP-NNN.md` with a task contract; this register is the index.

## Register

| IMP | Theme | Status | Priority | Evidence / Source |
|-----|-------|--------|----------|-------------------|
| IMP-001 | Comms benchmark: P4 (topics_parent) churn replicates — re-measure the ~6× churn hypothesis | Proposed | Medium | `04-verification/communication-structures/FINDINGS.md` "flagged as a hypothesis… n=1"; DL-11 |
| IMP-002 | Multi-agent: workspace mechanics (scoped shared surface + visibility + append/review) and round/cadence semantics | Proposed | High | INVESTIGATION next-steps; DL-7 hybrid needs a defined shared surface |
| IMP-003 | Multi-agent: equivocality heuristic (write vs message; bias workspace-first) | Proposed | Medium | INVESTIGATION next-step; the channel rule must be non-prompt advice |
| IMP-004 | Multi-agent: `introduce` mechanism (delegation-time `collaborate_with` vs mid-run tool vs both) | Proposed | Medium | INVESTIGATION next-step; B-curated requires explicit membership (Hackman) |
| IMP-005 | Mechanize verification: report-time acceptance gate (`verify_children=true`); gap G1 | Proposed | High | `04-verification/gap-analysis/README.md` G1 (P0, open); AD-005/AD-006 — breaks "verify before synthesize" as a guarantee |
| IMP-006 | Maintain decision log + traceability map as living registers | Proposed | Medium | Restructuring review GAP-1/GAP-2; ADR/decision-log reconciliation rule |
| IMP-008 | Budgeting / cost control (request-budget tool + hard token cap) | Proposed | Medium | `04-verification/gap-analysis/README.md` G8 (P1, open) — dead plumbing; cost is the stated #1 motivation |
| IMP-009 | Durable heal budgets across process restart | Proposed | Low | `04-verification/gap-analysis/README.md` G13 (P2, open) |
| IMP-010 | Agent-facing provenance / trace tool | Proposed | Low | `04-verification/gap-analysis/README.md` G12 (P2, open) |
| IMP-011 | USD-cost reporting in runtime/CLI | Proposed | Low | `04-verification/gap-analysis/README.md` G9 (P2, open) |
| IMP-012 | Docs drift cleanup (tool count 19, prompt path `core/prompts.py`, Layer-2 naming) | Proposed | Low | `04-verification/gap-analysis/README.md` G7/G11 |
| IMP-013 | External-benchmark scaffolding (Terminal-Bench mini / GAIA adapter as opt-in pipelines) | Proposed | Low | `../05-operation/guides/benchmark-alternatives/README.md` verdicts; suggestion thread "evaluate external agents / benchmarks" |
| IMP-014 | Trace send/receive for simpler debugging | Proposed | Low | `06-evolution/backlog.md` ("make the trace send and receive") |
| IMP-015 | Tight fallback loop before failing at tool-call limits (loop-point-out + recover) | Proposed | Low | `06-evolution/backlog.md` ("tighter fallback loop… point out it's looping and see if it can recover") |
| IMP-016 | Refactor `product-breakdown` nodes to the AD-009 budget (empty and remove the size allow-list) | Completed | Medium | AD-009 / DL-17; allow-list emptied and mechanism removed; `check_node_size.py --strict` clean |

## Notes on provenance

- **IMP-001** comes from the verification evidence chain (`04-verification/communication-structures/FINDINGS.md` n=1 churn hypothesis); **IMP-002..005** migrate the multi-agent INVESTIGATION's open next-steps (all under `02-architecture/multi-agent-coordination/INVESTIGATION.md` "Investigation next steps"; completed ones are marked `[x]` there and are NOT re-registered here); **IMP-006** migrates the restructuring review's GAP-1/GAP-2 (living registers).
- **IMP-008..012** migrate the open gaps of `04-verification/gap-analysis/README.md` (G7, G8, G9, G11–G13); G1 is now IMP-005. Resolved gaps (G2–G6, G10) are NOT re-registered.
- **IMP-013..015** come from unresolved/unpicked suggestions in `06-evolution/backlog.md`.
- **IMP-016** completed the node-model refactor (AD-009): every node is within budget and `tools/node_size_allowlist.txt` (and its mechanism) is removed.
- All other statuses are **Proposed** until an IMP is written to `selected/` and Selected.

## Task-contract seed (mandatory before code changes)

Every IMP selected for work must carry a task contract before any code changes — IMP template fields: **Objective** (what "done" looks like), **Scope** (what is in scope), **Acceptance** (verifiable acceptance criteria), **Out Of Scope**, plus Evidence, Risk And Blast Radius, Dependencies, and Traceability. Selection is recorded in the IMP file header (`Lifecycle Stage: Selected`, `Selected Date`). This mirrors the repo's own rule: candidates justify themselves before implementation.

## Stale-pointer notice

`06-evolution/backlog.md` previously instructed future runs to "use docs/roadmap/LIVE_CAPITAL_READINESS.md — a to-do list for tracking… unsupervised live capital." That path never existed. **This file is the roadmap.** The live-capital readiness item (should it ever be pursued) is captured here under IMP-013's theme; no separate `docs/roadmap/` tree will be created.