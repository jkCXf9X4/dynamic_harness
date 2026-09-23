---
title: "Acceptance criteria — CLI"
category: requirement
summary: >
  Observable checks that the terminal stays prompt-only and the persisted
  overview/tree behave as specified.
related:
  - fr-terminal.md
  - fr-persisted-overview.md
  - fr-live-surface.md
---

# Acceptance criteria

- Running `dynamic-harness "task"` prints only: the outcome line, an aggregate,
  and the state-file paths — no tree/dashboard.
- During a run, `tail -f <run>/agents.txt` shows agents appearing and status /
  message / token counts progressing (messages are the cumulative count sent to
  the LLM, so they persist after an agent completes).
- `/tree` in the interactive terminal prints a box-drawn tree of
  id/status/messages/tokens matching `agent_tree.json`.
- During a run, typing a message either queues it (busy) or interrupts the
  child-wait (idle), and typing `/tree` prints a live status snapshot without
  disrupting the run.
- A non-TTY batch run prints no token counter/input artifacts.
- The CLI imports with no Rich rendering dependency if Rich is removed from the
  `cli/present.py` render path.
