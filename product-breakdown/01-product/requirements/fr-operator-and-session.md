---
title: "FR-4..FR-6 — Operator evaluation, session continuity, traceability"
category: requirement
summary: >
  A quick plain-text tree for spotting stuck/runaway agents; the REPL keeps one
  root agent across turns; provenance and overview files survive the process.
related:
  - fr-persisted-overview.md
  - direction.md
---

# FR-4..FR-6. Operator evaluation, session continuity, traceability

## FR-4. Quick operator evaluation

- **FR-4.1** The operator can view a plain-text agent tree showing per-agent
  `[status]`, message count, and token usage — on the terminal via `/tree` and
  on disk via `agents.txt`.
- **FR-4.2** The tree is sufficient to spot a stuck, looping, or cost-runaway
  agent (a high message/token count with a non-terminal status).

## FR-5. Interactive session continues the same root agent

- The `-i` / default REPL keeps the same root agent across turns
  (`root_agent`), so the operator can iterate on a task conversationally.

## FR-6. Traceability after exit

- Provenance and overview files (traces, artifacts, commits, plus the overview
  files above) survive the process, so a run is fully auditable afterwards.
