---
title: "Use-Case — Pipelines & Long Jobs"
category: use-case
summary: >
  Batch extraction/transformation over many files, and long multi-step jobs:
  the manyfiles pattern (one item at a time, write each result), prune/restore,
  and checkpoint/resume that makes an interrupted overnight job recoverable.
related:
  - ../../02-architecture/concepts/agent-lifecycle/README.md
  - ../../02-architecture/concepts/artifact-system/README.md
  - ../../02-architecture/concepts/self-healing/README.md
  - ../../02-architecture/examples/execution_patterns.md
---

# Pipelines & Long Jobs

Mechanically repetitive, long tasks: process N items one at a time, or walk a
large workspace serially. Two disciplines decide success — **write-as-you-go**
(each result written to disk immediately, so progress survives interruption) and
**`prune`/`restore` + checkpoint resume** (the rot defense and post-crash path).

## Scenario A — Batch sizing / inventory (the `manyfiles` pattern)

> "There is a `resources/_payload/` directory with many files. Compute and record
> the byte size of EVERY file, one at a time: list all files, for each run
> `wc -c <file>` and append `<name>:<size>` to `.optimize_benchmarks/sizes.txt`,
> one file per turn; `prune()` turns for files already written. Report when done."

**Why it fits:** the benchmark `FileSizesTask` maps exactly — sequential
single-command calls whose outputs *stale the moment the next file starts*;
write-as-you-go + `prune()` is the designed antidote.

## Scenario B — Pipeline extraction across a tree

> "Find every `config.json` in `services/`, validate it against our schema class,
> and write a `issues.csv` with one row per failing file (path, missing field,
> sample). Leave valid files untouched. Keep the run resumable."

**Why it fits:** same write-as-you-go + prune discipline; `read`/`grep` discover
targets, content is aggregated, rows written as validated. A hard cap on turns
per item with escalation/retry prevents one bad file grinding the tree.

## Scenario C — Headless job monitoring via persisted overview

> "Run the nightly extraction job as a background process. Monitor its progress,
> and surface a link or file the ops team can tail."

The prompt-only CLI lets the job run batch-style without dashboard noise, its
progress streamed to the run directory. Ops tooling tails `agents.txt` (tree,
`events.jsonl` (tool calls), `stats.json`, and `checkpoints/`, then
`--resume <agent_id>` after a restart, instead of a status TUI.

## Resumability (self-healing for jobs)

1. **Checkpoint**: the run loop auto-persists an `AgentCheckpoint` each committed
   turn; `/checkpoints` lists resumable agents.
2. **Resume**: `--resume <agent_id>` (CLI) or `Runtime.resume(agent_id)` (async)
   rebuilds it from the checkpoint and continues to completion.
3. **Rot recovery**: on repeated calls / max-iterations, Layer-3 re-delegates a
   fresh worker **reusing the partial on-disk result**.

## Verification & acceptance

Verify the *artifact*, not the summary: confirm per-row counts add up to the
actual file inventory (`glob`) and re-run `wc -c` on a sample; for interrupted
runs, compare the on-disk resume **evidence** rather than re-computing the tree.

## Fit checklist & caveats

- **Fits well**: bounded item counts, verifiable per-item ground truth, any
  workload that *writes as it goes*.
- **Strain / watch**: define the terminal condition exactly (an open-ended crawl
  is a spec problem), and remember `bash` has no pipes/redirects.
- **Not a fit**: interactive "watching" loops; work is one run (resumable), then
  terminate — monitor a live run by tailing the overview files, not a TUI.
