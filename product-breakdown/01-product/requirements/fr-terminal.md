---
title: "FR-1 — Prompt-only terminal"
category: requirement
summary: >
  The terminal accepts a task prompt, prints the final outcome and an aggregate,
  and renders no live dashboard.
related:
  - direction.md
---

# FR-1. Prompt-only terminal

- **FR-1.1** The terminal accepts a task prompt (batch or interactive `-i`).
- **FR-1.2** Batch runs print the final outcome (report summary or failure
  reason), one aggregate line (agent/commit/token counts), and the persisted
  state file paths.
- **FR-1.3** No live dashboard (no Rich `Live`, no tree/status rendered to the
  terminal during the run).
