---
id: INFO-128
type: info
title: Customizing the Benchmark
summary: To add, remove, or change a task, edit and register it in `src/dynamic_harness/benchmark/tasks.py` (`ALL_TASKS`).
date: 2026-09-23
status: current
---

# Customizing the Benchmark

To add, remove, or change a task, edit `src/dynamic_harness/benchmark/tasks.py`
and register it in `ALL_TASKS`. Each task is a `BenchmarkTask` subclass with a
**failable** ground-truth `verify()` that compares the agent's output artifact
against computed ground truth. Because `ALL_TASKS` is the single front, the
change automatically applies to the general optimization, the prune/restore A/B,
and the CLI. To tune what the optimizer searches for (e.g. pruning), edit
`prompts/generate_variants.prompt` and `prompts/refine_variants.prompt`; to
reweight the objective, edit `src/dynamic_harness/benchmark/scoring.py`.

## Owns
- How to add, remove, or change a benchmark task and register it in `ALL_TASKS`
- How to tune the optimizer's search objective (variant prompts, scoring)

## Excludes
- What each task checks and why it is included: `INFO-134`
- How to run the optimization: `INFO-133`
