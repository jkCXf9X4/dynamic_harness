# How to Run

Clean the benchmark state, then run the optimization:

```bash
rm -rf .optimize_benchmarks/*
source venv/bin/activate
python scripts/run_optimize.py
```

- The script uses generation/refinement agents (`prompts/generate_variants.prompt`,
  `prompts/refine_variants.prompt`) to write variant prompts to
  `.optimize_benchmarks/variants.json` / `variants_round2.json`, then measures
  every (prompt, task) pair with the deterministic `Benchmark` harness against
  `ALL_TASKS` and ranks on data.
- Live output prints each delegation and tool call; the final `=== RESULTS ===`
  block summarizes the best prompt, pass fraction, token/cost/turn totals, and
  total time.
- Expect several minutes to ~10+ minutes depending on model and task count.

> The runner deliberately calls `trace_store.clear()` before each run to avoid
> stale trace data. Benchmark files persist under `.optimize_benchmarks/`.

## Smoke Test

To sanity-check the pipeline without a full run, use the standalone metric CLI
against a single prompt (`--seed-only` runs only the default prompt):

```bash
source venv/bin/activate
python -m dynamic_harness.benchmark.run --seed-only
```

This runs every task in `ALL_TASKS` against the seed prompt and prints the
verification verdict per task.
