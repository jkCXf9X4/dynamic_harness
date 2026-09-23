---
title: "CLI Direction & Requirements — Direction"
category: requirement
summary: >
  Why the CLI is minimal and prompt-only: status/tree/event telemetry is
  persisted to files so a run can be driven headlessly and inspected by other
  tooling.
related:
  - ../../05-operation/guides/getting-started.md
  - ../use-cases/pipelines-and-jobs.md
  - ../../00-intent/VISION.md
---

# Direction

The CLI is intentionally **minimal and prompt-only**. Status, agent tree, and
event telemetry are **persisted to files** under the run directory rather than
rendered in a terminal dashboard. This makes the application composable in a
larger automated workflow: the same run can be driven headlessly, its progress
streamed to disk, and its output inspected by other tooling.

Prompts and the final outcome are printed to the terminal; everything else that
was previously rendered live (agent tree, status, events) is written to files
for traceability and overview.
