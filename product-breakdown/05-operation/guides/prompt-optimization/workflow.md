# What This Does

Given the baseline prompt (`src/dynamic_harness/core/agent_system_prompt.txt`),
an **orchestrator agent** runs a two-round A/B test:

- **Round 1** — generates 5 variants + tests all 6 prompts (seed + 5) against the benchmark task suite.
- **Round 2** — takes the top 3, generates 3 refined variants, tests 6 prompts again.
- Aggregates results and writes the single best prompt to disk.

All measurement/ranking is deterministic and in-process: each (prompt, task)
pair is run by a fresh `Runtime` in a staged snapshot workspace and verified
against a **failable ground-truth verifier** (see `dynamic_harness.benchmark`).
The LLM only performs creative variant generation; it never solves or ranks the
tasks.

The benchmark tasks come from **one canonical source**:
`src/dynamic_harness/benchmark/tasks.py` (`ALL_TASKS`). That same list drives the
general optimization (`scripts/run_optimize.py`), the dedicated prune/restore
A/B (`scripts/run_prune_ab.py`), and the standalone CLI
(`python -m dynamic_harness.benchmark.run`). There is no second,
prose-embedded task list to keep in sync.
