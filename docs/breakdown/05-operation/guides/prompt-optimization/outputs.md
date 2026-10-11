---
id: INFO-131
type: info
title: Outputs
summary: After a full run, `.optimize_benchmarks/` contains the variant prompts, per-run metrics, and the single best prompt
date: 2026-09-23
status: current
---

# Outputs

After a full run, `.optimize_benchmarks/` contains:

- **`variants.json`**
  - Round-1 variant prompts
- **`variants_round2.json`**
  - Round-2 variant prompts
- **`round1.json`**
  - Round-1 per-run metrics
- **`round1.md`**
  - Round-1 ranked report
- **`round2.json`**
  - Round-2 per-run metrics
- **`round2.md`**
  - Round-2 ranked report
- **`best_prompt.txt`**
  - **The single best system prompt (complete text)**
- **Task artifacts**
  - `largest_files.txt`
  - `fibonacci.py`
  - `test_fibonacci.py`
  - `todos.txt`
  - `sizes.txt`

The prune/restore A/B (`.optimize_ab/`) writes `on/bench.*` and `off/bench.*`
plus a printed comparison.

## Owns
- What a full optimization run writes to `.optimize_benchmarks/`
- What the prune/restore A/B writes to `.optimize_ab/`

## Excludes
- How to apply the winning prompt: `INFO-129`
- How to run the optimization: `INFO-133`
