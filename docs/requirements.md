---
title: "CLI Direction & Requirements"
category: requirement
summary: >
  Requirements governing the CLI surface and the persisted overview. The CLI is
  kept minimal and prompt-only; all telemetry is written to files, making the
  tool composable as part of larger automated workflows.
related:
  - ../guides/getting-started.md
  - ../use-cases/pipelines-and-jobs.md
  - ../VISION.md
---

# CLI Direction & Requirements

## Direction

The CLI is intentionally **minimal and prompt-only**. Status, agent tree, and
event telemetry are **persisted to files** under the run directory rather than
rendered in a terminal dashboard. This makes the application composable in a
larger automated workflow: the same run can be driven headlessly, its progress
streamed to disk, and its output inspected by other tooling.

> Prompts and the final outcome are printed to the terminal; everything else
> that was previously rendered live (agent tree, status, events) is written to
> files for traceability and overview.

## Functional Requirements

### FR-1. Prompt-only terminal

- **FR-1.1** The terminal accepts a task prompt (batch or interactive `-i`).
- **FR-1.2** Batch runs print the final outcome (report summary or failure
  reason), one aggregate line (agent/commit/token counts), and the persisted
  state file paths.
- **FR-1.3** No live dashboard (no Rich `Live`, no tree/status rendered to the
  terminal during the run).

### FR-2. Persisted overview

Every run writes a continuously-refreshed overview to the **run root** (the
parent of `artifacts/`, `repo/`, and `traces/`):

- **FR-2.1** `agents.txt` — plain-text agent tree (id, status, description,
  messages, token usage), rewritten on every terminal event. Watchable while a
  run is live.
- **FR-2.2** `agent_tree.json` — same tree as structured JSON for machine use.
- **FR-2.3** `stats.json` — aggregate agent/commit/token counts.
- **FR-2.4** `events.jsonl` — append-only structured event stream
  (report/failure/escalation/activity).
- **FR-2.5** `index.jsonl` — flat artifact→agent/task/path map, written after
  the run when artifacts exist.

### FR-3. Visible "progress is happening"

While a run is active the terminal shows a lightweight single-line token
counter whose (optional) label reflects the latest activity (tool calls,
delegations, compression, self-heal). The indicator must not corrupt the
terminal output; the agent `ask` interaction pauses it while prompting on
stdin.

### FR-4. Quick operator evaluation

- **FR-4.1** The operator can view a plain-text agent tree showing per-agent
  `[status]`, message count, and token usage — on the terminal via `/tree` and
  on disk via `agents.txt`.
- **FR-4.2** The tree is sufficient to spot a stuck, looping, or cost-runaway
  agent (a high message/token count with a non-terminal status).

### FR-5. Interactive session continues the same root agent

- The `-i` / default REPL keeps the same root agent across turns
  (`root_agent`), so the operator can iterate on a task conversationally.

### FR-6. Traceability after exit

- Provenance and overview files (traces, artifacts, commits, plus the overview
  files above) survive the process, so a run is fully auditable afterwards.

## Non-functional requirements

- **NFR-1. Composability** — the terminal must be usable inside a pipeline:
  batch mode produces a deterministic exit report (outcome line + state files)
  and no dashboard clutter.
- **NFR-2. Isolation of rendering** — the presentation layer
  (`cli/present.py`) is pure text/JSON view-models with no terminal-library
  dependency, so it can render to console *or* disk without coupling.
- **NFR-3. Cheap live helpers** — the token counter is a single background
  asyncio task with no new dependencies and no live-dashboard machinery.
- **NFR-4. Atomic, append-only event log** — `events.jsonl` is append-only to
  allow tailing; tree/stats snapshots are atomic rewrites (write-then-replace).

## Acceptance criteria

- Running `dynamic-harness "task"` prints only: the outcome line, an aggregate,
  and the state-file paths — no tree/dashboard.
- During a run, `tail -f <run>/agents.txt` shows agents appearing and status /
  message / token counts progressing.
- `/tree` in the interactive terminal prints a box-drawn tree of
  id/status/messages/tokens matching `agent_tree.json`.
- The CLI imports with no Rich rendering dependency if Rich is removed from the
  `cli/present.py` render path.