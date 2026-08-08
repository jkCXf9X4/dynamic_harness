# Prompt Optimization — How to Run & Feed Back the Result

Portable reference for the two-stage A/B-test workflow that optimizes the
Dynamic Harness agent system prompt. Covers how to run it, what the inputs and
outputs are, and how to feed the winning prompt back into the application.

---

## 1. What this does

Given the baseline prompt (`src/dynamic_harness/core/agent_system_prompt.txt`),
an **orchestrator agent** runs a two-round A/B test:

- **Round 1** — generates 5 variants + tests all 6 prompts (seed + 5) against
  the benchmark task suite.
- **Round 2** — takes the top 3, generates 3 refined variants, tests 6 prompts
  again.
- Aggregates results and writes the single best prompt to disk.

All measurement/ranking is deterministic and in-process: each (prompt, task)
pair is run by a fresh `Runtime` in a staged snapshot workspace and verified
against a **failable ground-truth verifier** (see `dynamic_harness.benchmark`).
The LLM only performs creative variant generation; it never solves or ranks the
tasks.

The benchmark tasks come from **one canonical source**:
`src/dynamic_harness/benchmark/tasks.py` (`ALL_TASKS`). That same list drives
the general optimization (`scripts/run_optimize.py`), the dedicated prune/restore
A/B (`scripts/run_prune_ab.py`), and the standalone CLI
(`python -m dynamic_harness.benchmark.run`). There is no second, prose-embedded
task list to keep in sync.

## 2. Files involved

| Role | Path |
|---|---|
| Single task source | `src/dynamic_harness/benchmark/tasks.py` (`ALL_TASKS`) |
| Optimization runner | `scripts/run_optimize.py` |
| Prune/restore A/B test | `scripts/run_prune_ab.py` |
| Standalone metric CLI | `src/dynamic_harness/benchmark/run.py` |
| Variant-generation instructions | `prompts/generate_variants.prompt` |
| Refinement instructions | `prompts/refine_variants.prompt` |
| Baseline prompt (the thing being optimized) | `src/dynamic_harness/core/agent_system_prompt.txt` |
| Model/provider config | `harness.json` |
| Runtime output (artifacts/commits/traces) | `.dynamic-harness/` |
| Optimization output files | `.optimize_benchmarks/` |
| Prune/restore A/B output files | `.optimize_ab/` |

## 3. Prerequisites

- Python 3.10+ with the package installed into the venv:
  ```bash
  source venv/bin/activate
  pip install -e .
  ```
- An OpenRouter API key set in the environment / `~/.bashrc`:
  ```bash
  export OPENROUTER_API_KEY=sk-...
  ```
- `harness.json` pointing at a model that can handle tool calls. The default
  uses DeepSeek flash and keeps the `provider_ignore` list to route around
  providers that cannot handle tool calling:
  ```json
  {
    "llm": {
      "model": "deepseek/deepseek-v4-flash",
      "base_url": "https://openrouter.ai/api/v1",
      "provider_ignore": ["gmicloud", "SiliconFlow", "Baidu"],
      "provider_allow_fallbacks": true
    },
    "safety": {
      "max_iterations": 500,
      "repeated_call_limit": 5
    }
  }
  ```

## 4. How to run

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

### Running just a smoke test

To sanity-check the pipeline without a full run, use the standalone metric CLI
against a single prompt (`--seed-only` runs only the default prompt):

```bash
source venv/bin/activate
python -m dynamic_harness.benchmark.run --seed-only
```

This runs every task in `ALL_TASKS` against the seed prompt and prints the
verification verdict per task.

## 5. Outputs

After a full run, `.optimize_benchmarks/` contains:

| File | Contents |
|---|---|
| `variants.json` / `variants_round2.json` | Round-1 / Round-2 variant prompts |
| `round1.json` / `round1.md`, `round2.json` / `round2.md` | Per-run metrics + ranked reports |
| `best_prompt.txt` | **The single best system prompt (complete text)** |
| Task artifacts | `largest_files.txt`, `fibonacci.py`, `test_fibonacci.py`, `todos.txt`, `sizes.txt` |

The prune/restore A/B (`.optimize_ab/`) writes `on/bench.*` and `off/bench.*`
plus a printed comparison.

## 5b. The task suite (one front)

All tasks live in `src/dynamic_harness/benchmark/tasks.py` and are consumed by
every entry point:

| id | What it checks | Why it's included |
|---|---|---|
| `discovery` | 3 largest `.py` files by size | basic file tooling |
| `codegen` | Fibonacci + assertions, run via `python3` | code generation + verification |
| `analysis` | TODO/FIXME scan correctness | search + reporting |
| `manyfiles` | byte sizes of every file in `_payload/`, processed one at a time | **long multi-step context**: ~16+ sequential tool calls, so it stresses and rewards `prune()`/`restore()` context management |

The `manyfiles` task is the pruning probe — it builds a large transcript of
stale tool results, so a system prompt that guides agents to `prune()` finished
turns (and `restore()` when needed) scores lower prompt-token counts without
losing correctness. That is what makes the optimizer search for pruning-aware
prompts.

## 6. Feeding the optimized prompt back to the application

The application loads its default system prompt **at import time**:

```python
# src/dynamic_harness/core/agent.py:26
AGENT_SYSTEM_PROMPT = (Path(__file__).parent / "agent_system_prompt.txt").read_text()
```

Any agent without an explicit `system_prompt` override uses this constant
(`agent.py:101`). There are three ways to apply the winning prompt:

### Option A (recommended) — replace the seed file
Overwrite the file with the optimized text so it becomes the new default:

```bash
cp .optimize_benchmarks/best_prompt.txt \
   src/dynamic_harness/core/agent_system_prompt.txt
```

The value is read once at module load, so the running process must be restarted
for the change to take effect. Back up the original:
```bash
cp src/dynamic_harness/core/agent_system_prompt.txt{,.bak}
```

### Option B — per-agent override (no file change)
Pass the prompt text as a `system_prompt` at agent creation:
```python
agent = Agent(agent_id, task, runtime, system_prompt=optimized_text)
```
For sub-agents created via the `delegate` tool, pass it via the tool's
`system_prompt` parameter. This keeps the global default untouched while
testing a candidate on specific agents only.

### Option C — programmatic task-level override
Set `Task.system_prompt = optimized_text` before delegating; the agent prefers
`task.system_prompt` over the module constant (`agent.py:48`).

### Important caveat
`best_prompt.txt` begins with a `### VARIANT ...` header line (the generator
labels variants). If writing it verbatim into `agent_system_prompt.txt`, strip
that first label line so only the prompt body is used:
```bash
tail -n +2 .optimize_benchmarks/best_prompt.txt > src/dynamic_harness/core/agent_system_prompt.txt
```

## 7. Rate limits & provider quirks

- Free-tier models (e.g. `:free` suffixes) hit per-minute rate limits and
  abort mid-run with `openai.RateLimitError: 429`. Use a paid/served model for
  full runs.
- `provider_ignore` routes around OpenRouter providers that mishandle tool
  calls. If the orchestrator returns empty output instead of tool calls, a
  guessed provider is refusing tools — add it to `provider_ignore`.
- Some models emit the **identical** `write()` call repeatedly. The harness
  fails that sub-agent after 5 identical batches (safety), and the `write`
  tool now returns a `"No change: content identical..."` message on identical
  content (`src/dynamic_harness/core/capabilities.py:_tool_write`) so agents
  recover instead of spinning.

## 8. Customizing the benchmark

To add, remove, or change a task, edit `src/dynamic_harness/benchmark/tasks.py`
and register it in `ALL_TASKS`. Each task is a `BenchmarkTask` subclass with a
**failable** ground-truth `verify()` that compares the agent's output artifact
against computed ground truth. Because `ALL_TASKS` is the single front, the
change automatically applies to the general optimization, the prune/restore A/B,
and the CLI. To tune what the optimizer searches for (e.g. pruning), edit
`prompts/generate_variants.prompt` and `prompts/refine_variants.prompt`; to reweight
the objective, edit `src/dynamic_harness/benchmark/scoring.py`.
