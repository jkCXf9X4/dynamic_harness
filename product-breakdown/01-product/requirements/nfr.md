---
title: "NFR-1..NFR-4 — Non-functional requirements"
category: requirement
summary: >
  Composability, rendering isolation, cheap live helpers, and an atomic
  append-only event log.
related:
  - direction.md
  - fr-persisted-overview.md
---

# Non-functional requirements

- **NFR-1. Composability** — the terminal must be usable inside a pipeline:
  batch mode produces a deterministic exit report (outcome line + state files)
  and no dashboard clutter.
- **NFR-2. Isolation of rendering** — the presentation layer (`cli/present.py`)
  is pure text/JSON view-models with no terminal-library dependency, so it can
  render to console *or* disk without coupling.
- **NFR-3. Cheap live helpers** — the input line runs in the foreground asyncio
  loop via `prompt_toolkit` (bracketed paste, multi-line input, history,
  wide-char/wrap handling are all delegated to it); no live-dashboard machinery
  (no Rich `Live`, no full-screen TUI) is used, keeping the run loop itself free
  of TUI dependencies. `prompt_toolkit` is the single input dependency added for
  the interactive surface.
- **NFR-4. Atomic, append-only event log** — `events.jsonl` is append-only to
  allow tailing; tree/stats snapshots are atomic rewrites (write-then-replace).
