---
title: "Self-Healing and Resume"
category: meta
summary: >
  Blunt-vs-rot diagnosis-driven recovery with a shared heal budget and a
  deliverable gate, plus checkpoint persistence that makes an interrupted run
  reconstructable across restarts.
parent: "README.md"
related:
  - ../../02-architecture/concepts/self-healing.md
---

# Self-Healing and Resume

## Blunt-vs-rot self-healing with a shared budget

Recovery is diagnosis-driven, not a blanket "always retry":

- **Blunt** (healthy context, single clearable error, prose answer, forgot the
  artifact) → **resume the same agent** with a focused nudge (Layer 1).
- **Rot** (repeated calls, max iterations, wall-clock timeout, repeated Layer-1
  misses) → **spawn a fresh worker** over the same task, injecting the failure
  reason and pointing at the dead worker's on-disk artifacts (Layer 3).
- **Structural** (impossible task, bad spec, willing non-compliance) →
  **escalate** (Layer 4). Never grind.

Two enforcement details separate this from prompt-level retry guidance:

- **Shared budget.** Parent-driven `resume` and runtime-driven self-heal consume
  the *same* per-child budget (`max_resumes` / `max_fresh_retries`), so retries
  cannot stack. The `resume` tool lets a parent force `"resume"` (refused on a
  rotted context — replaying poison repeats the failure) or `"fresh"`.
- **The deliverable gate.** A child that completes *in prose* — no artifact, no
  `files_written` — is treated as a failure and healed, at both the root and the
  delegate boundary (`_has_deliverable`). This catches the most common silent
  failure mode.

## Checkpoint persistence and resumability

The run loop auto-persists a structured `AgentCheckpoint` after **every**
committed turn. `Runtime.resume(agent_id)` rebuilds a live agent from disk —
across process restarts — and the CLI exposes `/resume`. Combined with the
immutable artifact + commit graph, a crashed or interrupted run is
reconstructable, not restarted.
