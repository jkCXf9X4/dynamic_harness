---
title: "Use-Case — Evaluation & QA"
category: use-case
summary: >
  Dogfooding the runtime as its own QA lab: run the deterministic benchmark
  suite, A/B-test system prompts, triage failures, and audit provenance — a
  first-class use-case thanks to the failable verifiers.
related:
  - ../../02-architecture/concepts/self-healing/README.md
  - ../../../docs/api/repository.md
  - ../../05-operation/guides/prompt-optimization/README.md
  - ../../05-operation/guides/benchmark-alternatives/README.md
---

# Evaluation & QA

The framework measures itself. Because every `BenchmarkTask` carries a
**failable ground-truth verifier**, "did the agent do the job" is a boolean, not
a vibe — which turns evaluation into a concrete, scriptable use-case.

## Scenario A — Regression-suite a change to the system prompt

> "After an agent-methodology edit, re-run the full benchmark suite and compare
> pass rate + token/cost totals against the previous baseline. Report the delta
> with failing-task diagnostics."

**Flow:** `python -m dynamic_harness.benchmark.run --seed-only` (or
`scripts/run_optimize.py`) runs every task in `ALL_TASKS` against the current
prompt, in a **staged snapshot workspace** with a fresh `Runtime` per task;
verifiers compare artifacts against computed ground truth; a change ships only if
the suite does not regress. **Why it fits:** deterministic verifiers +
fresh-context isolation give *reproducible* measurements for a CI gate.

## Scenario B — A/B-testing prompt variants

The optimizer workflow: an orchestrator agent generates candidate prompts (LLM
for creativity only), the runner measures every (prompt, task) pair and ranks on
data, then writes `best_prompt.txt` with provenance (`.optimize_benchmarks/`) —
the framework improving itself.

## Scenario C — Failure triage with provenance

> "Given a failed batch run, produce an incident note: which agent failed, at
> which turn, which tool call, the failure reason, and whether the rot
> discriminator classified it blunt-vs-rot."

**Flow:** `/provenance <id>` (CLI) maps task → trace → artifacts → commits;
`/trace <id>` points at `trace.jsonl`; run-level `index.jsonl` maps
artifact→agent. A QA agent reads these on-disk records and synthesizes a
diagnosis — **failure analysis does not require rerunning** because artifacts +
traces are immutable and greppable by a child that never re-executes the work.

## Scenario D — QA gate for a library consumer

Embed `Harness`/`Runtime` behind a CI job: run a golden-task suite against a
consuming repo, capture `agent_count`, `total_usage`, and `commit_count`, fail
the job if any root agent does not complete. Event handlers (`on_report`,
`on_failure`) wire verdicts straight into the pipeline's output.

## Verification & acceptance

- The **verifier** is ground truth; accept/reject is `verify(output_dir,
  scan_root)`, never the agent's self-reported summary. Baseline comparisons must
  share the same task list (`ALL_TASKS` single source) and staged-workspace
  procedure to be meaningful.

## Fit checklist & caveats

- **Fits well**: prompt optimization, regression gates, flake/rot triage,
  provenance-based incident reports.
- **Strain**: evaluation at *production LLM scale* (hundreds of runs) is a batch
  pipeline — schedule via the runner, let agents only interpret artifacts.
- **Watch**: the verifier must be *failable* — a "success" that can never fail is
  not a gate; keep one canonical task source to avoid drift.
