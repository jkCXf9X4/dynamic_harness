---
id: INFO-134
type: info
title: The Task Suite (One Front)
summary: All tasks live in `src/dynamic_harness/benchmark/tasks.py` and are consumed by every entry point
date: 2026-09-23
status: current
---

# The Task Suite (One Front)

All tasks live in `src/dynamic_harness/benchmark/tasks.py` and are consumed by
every entry point:

- **`discovery`**
  - Checks: 3 largest `.py` files by size
  - Why: basic file tooling
- **`codegen`**
  - Checks:
    - Fibonacci + assertions
    - run via `python3`
  - Why: code generation + verification
- **`analysis`**
  - Checks: TODO/FIXME scan correctness
  - Why: search + reporting
- **`manyfiles`**
  - Checks:
    - byte sizes of every file in `resources/_payload/`
    - processed one at a time
  - Why: **long multi-step context**
    - ~16+ sequential tool calls
    - stresses and rewards `prune()`/`restore()` context management
- **`parallel`**
  - Checks:
    - 8 independent sum-of-squares sub-tasks
    - one per `resources/_parallel/*/input.txt`
  - Why: **delegation probe**
    - an agent is told to delegate one child per subdirectory
    - metrics (`agent_count`, `max_depth`, `turns`) reveal whether the parallel parent-split shape is actually used
- **`synthesis`**
  - Checks:
    - one combined `synthesis.txt`
    - covering every first-line token in `resources/_sources/*.txt`
  - Why: **delegation/spawn probe**
    - children gather fragments
    - the parent fuses them into a single artifact
    - the "decompose to gather to fuse" shape

The `manyfiles` task is the pruning probe — it builds a large transcript of
stale tool results, so a system prompt that guides agents to `prune()` finished
turns (and `restore()` when needed) scores lower prompt-token counts without
losing correctness. That is what makes the optimizer search for pruning-aware
prompts. The `parallel` and `synthesis` tasks probe the *other* axis: whether
the prompt steers the agent to delegate independent sub-problems instead of
serializing them in one context.

## Owns
- What each benchmark task checks and why it is included
- The pruning probe (`manyfiles`) and the delegation probes (`parallel`, `synthesis`)

## Excludes
- How to add, remove, or change a task: `INFO-128`
- How the task suite is consumed by each entry point: `INFO-135`
