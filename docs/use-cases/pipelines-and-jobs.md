---
title: "Use-Case — Pipelines & Long Jobs"
category: use-case
summary: >
  Batch extraction/transformation over many files, and long multi-step jobs.
  Covers the manyfiles pattern (process one item at a time, write each result),
  the prune/restore discipline that keeps prompt tokens bounded, and the
  checkpoint/resume self-healing that makes an interrupted overnight job
  recoverable instead of restartable.
related:
  - concepts/agent-lifecycle.md
  - concepts/artifact-system.md
  - concepts/self-healing.md
  - ../examples/execution_patterns.md
---

# Pipelines & Long Jobs

Tasks that are mechanically repetitive and long: process N items, one at a
time; or walk a large workspace serially and reap structured data. Two tools
decide success here:

- **write-as-you-go** — each item's result is appended/written to a disk
  artifact immediately, so progress survives any interruption.
- **`prune`/`restore` + checkpoint resume** — the built-in defense against the
  context rot this shape tends to create, and the path back after a crash.

## Scenario A — Batch sizing / inventory (the `manyfiles` pattern)

> "There is a `_payload/` directory with many files. Compute and record the byte
> size of EVERY file, one at a time.
> List all files in `_payload/`; for each, run `wc -c <file>`, and append
> `<name>:<size>` to `.optimize_benchmarks/sizes.txt`. Process one file per
> turn, write each result as soon as you have it, and `prune()` turns for files
> already written to disk. When all are done, report with the artifact."

**Why it fits:** the benchmark `FileSizesTask` maps exactly: sequential
single-command calls whose outputs are *stale the moment the next file starts*.
Writing each line to disk before moving on (write-as-you-go) + `prune()` of done
turns is the designed antidote to the long-transcript rot problem this workload
bloats.

## Scenario B — Pipeline extraction across a tree

> "Find every `config.json` in `services/`, validate it against our schema
> class, and write a `issues.csv` with one row per failing file (path, missing
> field, sample). Leave valid files untouched. Keep the run resumable."

**Why it fits:** same write-as-you-go + prune discipline; `read`/`grep` to
discover targets, `read` each file's current content, aggregate, and write rows
as they are validated. A hard cap on turns per item with escalation/retry
prevents a single bad file from grinding the whole tree.

## Resumability (self-healing for jobs)

For a long job that may be *interrupted* (a crash, a timed-out batch call, a
stopped container):

1. **Checkpoint**: the run loop auto-persists an `AgentCheckpoint` after every
   committed turn; the `/checkpoints` TUI command and the on-disk store list
   resumable agents.
2. **Resume**: `--resume <agent_id>` (CLI) or `Runtime.resume(agent_id)` (async)
   rebuilds the agent from the persisted checkpoint and continues to completion.
3. **Rot recovery**: if the rot discriminator fires (repeated identical calls /
   max-iterations), Layer-3 machinery re-delegates a fresh worker **reusing the
   partial on-disk result** — disk preserves progress, freshness cures rot.

## Verification & acceptance

- Verify the *artifact* (the appended file), not the summary: confirm per-row
  counts add up to the actual file inventory (`glob`), and re-run `wc -c` on a
  sample to confirm sizes.
- For interrupted runs, compare the resume **evidence** (the on-disk results
  file) rather than re-computing the whole tree.

## Fit checklist & caveats

- **Fits well**: bounded item counts, verifiable per-item ground truth, and
  any workload that *writes as it goes*.
- **Strain**: an open-ended crawl ("size everything, then every subfolder,
  then...") is a spec problem — the task must define the terminal condition
  exactly (this is also why `FileSizesTask` names the whole `_payload/` tree).
- **Watch**: `bash` has no pipes/redirects, so "`ls | wc -l`" must be
  decomposed into plain single commands; sort/aggregate in Python or `sort`/`uniq`
  as separate calls.
- **Not a fit**: interactive "watching" loops; an agent is not a long-running
  daemon — work is one run (resumable), then terminate.