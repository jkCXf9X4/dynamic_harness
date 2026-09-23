# Benchmark Runners

## Prompt Benchmark CLI (metric-driven)

```bash
python -m dynamic_harness.benchmark.run          # compare SEED + variants
python -m dynamic_harness.benchmark.run --seed-only
python -m dynamic_harness.benchmark.run --report profile
```

Compares prompts against all tasks from the single canonical task source `src/dynamic_harness/benchmark/tasks.py` (`ALL_TASKS`), ranked by a weighted rubric; metrics written to `.optimize_benchmarks/metrics.json` / `.md`. Variants are read from a JSON file mapping `prompt_id -> system_prompt text` (or null = seed). Needs `OPENROUTER_API_KEY` + `harness.json` pointing at a tool-calling model (default: deepseek flash with a `provider_ignore` list).

Related optimization runners (see [guides/prompt-optimization](../guides/prompt-optimization/README.md)):

```bash
python scripts/run_optimize.py      # two-round A/B prompt optimization
python scripts/run_prune_ab.py      # prune/restore A/B test
```

## Comms Benchmark (real-LLM topology comparison)

```bash
python -m dynamic_harness.benchmark.run_comms --smoke                      # sanity pass (1 cell)
python -m dynamic_harness.benchmark.run_comms                              # all cells, both tasks
python -m dynamic_harness.benchmark.run_comms --cells off,shared,topics_parent
python -m dynamic_harness.benchmark.run_comms --tasks interdependent --replicates 2
```

Each cell = one `communication.topology` value; everything else (task, LLM, workspace snapshot) identical. Unclean runs are re-attempted `--retries` times. Results (markdown report + raw `metrics-cells.json`) are written under `../04-verification/communication-structures/`. **Caution:** real-LLM runs cost tokens and time; the 2026-09-18 run took up to ~15 min / ~0.8–5.2M tokens per cell (per FINDINGS.md). Use `--smoke` first; treat small-n results as variance, not truth (n=1 caveat).

## Performance / Scaling Diagnostics

```bash
python -m dynamic_harness.benchmark.profile_scaling          # full grid
python -m dynamic_harness.benchmark.profile_scaling --quick  # fast sanity pass
```

Mock-LLM scaler isolating four axes (checkpoint cost, bytes/token sent per turn, CLI snapshot cost, end-to-end). See [guides/performance-diagnostics](../guides/performance-diagnostics/README.md).
