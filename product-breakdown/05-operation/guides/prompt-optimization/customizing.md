# Customizing the Benchmark

To add, remove, or change a task, edit `src/dynamic_harness/benchmark/tasks.py`
and register it in `ALL_TASKS`. Each task is a `BenchmarkTask` subclass with a
**failable** ground-truth `verify()` that compares the agent's output artifact
against computed ground truth. Because `ALL_TASKS` is the single front, the
change automatically applies to the general optimization, the prune/restore A/B,
and the CLI. To tune what the optimizer searches for (e.g. pruning), edit
`prompts/generate_variants.prompt` and `prompts/refine_variants.prompt`; to
reweight the objective, edit `src/dynamic_harness/benchmark/scoring.py`.
