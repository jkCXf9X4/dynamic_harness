---
title: "Use-Case — Evaluation & QA"
category: use-case
summary: >
  Dogfooding the runtime as its own QA lab: run the deterministic benchmark
  suite, A/B-test system prompts, triage agent failures, and audit a run's
  provenance. The framework's benchmark/verifier design makes evaluation a
  first-class use-case rather than an afterthought.
related:
  - concepts/self-healing.md
  - concepts/agent-lifecycle.md
  - api/repository.md
  - ../guides/prompt-optimization.md
---

# Evaluation & QA

The framework measures itself. Because every `BenchmarkTask` carries a
**failable ground-truth verifier**, "did the agent do the job" is a boolean,
not a vibe — and that property turns evaluation into a concrete, scriptable
use-case.

## Scenario A — Regression-suite a change to the system prompt

> "After an agent-methodology edit, re-run the full benchmark suite and compare
> pass rate + token/cost totals against the previous baseline. Report the delta
> with the failing-task diagnostics."

**Flow:** `python -m dynamic_harness.benchmark.run --seed-only` (or the full
`scripts/run_optimize.py`) runs every task in `ALL_TASKS` against the current
prompt, in a **staged snapshot workspace** with a fresh `Runtime` per task;
verifiers compare produced artifacts against computed ground truth. A prompt
change is only shipped if the suite does not regress (see
`guides/prompt-optimization.md` §6 for applying the winning prompt).

**Why it fits:** deterministic verifiers + fresh-context isolation give
*reproducible* measurements — exactly the property any CI regression gate needs.

## Scenario B — A/B-testing prompt variants

The optimizer workflow itself: an orchestrator agent generates candidate
prompts (LLM for creativity only), then the runner measures every
(prompt, task) pair and ranks on data, then writes `best_prompt.txt`. This
is the framework being used to improve the framework — and its output is
itself an artifact with provenance (`.optimize_benchmarks/`).

## Scenario C — Failure triage with provenance

> "Given a failed batch run, produce an incident note: which agent failed, at
> which turn, which tool call, the failure reason, and whether the rot
> discriminator classified it blunt-vs-rot."

**Flow:** `/provenance <id>` (CLI) maps task → trace → artifacts → commits;
`/trace <id>` points at the `trace.jsonl`; the run-level `index.jsonl` maps
artifact→agent. A QA agent reads these on-disk records and synthesizes a
diagnosis. This is the "audit trail" capability made useful: **failure analysis
does not require rerunning** because the artifacts + traces are immutable.

**Why it fits:** artifacts are write-once, commits give Git-like history, and
traces are JSONL — all greppable by a child agent that never re-executes the
original work.

## Scenario D — QA gate for a library consumer

Embed `Harness`/`Runtime` behind a CI job: run a golden-task suite against a
consuming repo, capture `agent_count`, `total_usage`, and `commit_count`, fail
the job if any root agent does not complete. Event handlers (`on_report`,
`on_failure`) wire verdicts straight into the pipeline's output.

## Verification & acceptance

- The **verifier** is ground truth; accept/reject is `verify(output_dir,
  scan_root)`, never the agent's self-reported summary.
- Baseline comparisons must share the same task list (`ALL_TASKS` single source)
  and the same staged-workspace procedure to be meaningful.

## Fit checklist & caveats

- **Fits well**: prompt optimization, regression gates, flake/rot triage,
  provenance-based incident reports.
- **Strain**: evaluation at *production LLM scale* (hundreds of runs) is a
  batch pipeline, not a single agent turn — schedule via the runner, and let
  agents only interpret the artifacts.
- **Watch**: verifier must be *failable* — a "success" that can never fail is
  not a gate; keep one canonical task source to avoid drift.