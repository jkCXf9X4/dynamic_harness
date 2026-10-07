---
id: INFO-017
type: info
title: "FR-2 — Persisted overview"
category: requirement
summary: >
  Every run writes a continuously-refreshed overview to the run root (the parent
  of artifacts/, repo/, and traces/).
related:
  - direction.md
  - ../use-cases/pipelines-and-jobs.md
date: 2026-09-23
status: current
---

# FR-2. Persisted overview

Every run writes a continuously-refreshed overview to the **run root** (the
parent of `artifacts/`, `repo/`, and `traces/`):

- **FR-2.1** `agents.txt` — plain-text agent tree (id, status, description,
  messages, token usage; live agents with their last activity and its age),
  rewritten continuously while a run is live (≈1/s heartbeat plus on every
  event). Watchable with `tail -f`.
- **FR-2.2** `agent_tree.json` — same tree as structured JSON for machine use.
- **FR-2.3** `stats.json` — aggregate agent/commit/token counts (+ write
  timestamp).
- **FR-2.4** `events.jsonl` — append-only structured event stream
  (report/failure/escalation/activity).
- **FR-2.5** `index.jsonl` — flat artifact→agent/task/path map, written after
  the run when artifacts exist.