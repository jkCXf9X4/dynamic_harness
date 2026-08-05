# Prompt Optimization — How to Run & Feed Back the Result

Portable reference for the two-stage A/B-test workflow that optimizes the
Dynamic Harness agent system prompt. Covers how to run it, what the inputs and
outputs are, and how to feed the winning prompt back into the application.

---

## 1. What this does

Given the baseline prompt (`src/dynamic_harness/core/agent_system_prompt.txt`),
an **orchestrator agent** runs a two-round A/B test:

- **Round 1** — generates 5 variants + tests all 6 prompts (seed + 5) against
  3 benchmark tasks = 18 runs.
- **Round 2** — takes the top 3, generates 3 refined variants, tests 6 prompts
  × 3 tasks = 18 runs.
- Aggregates results and writes the single best prompt to disk.

The orchestrator explicitly does **not** solve the benchmark tasks itself — it
delegates each (prompt, task) pair to a sub-agent for evaluation.

## 2. Files involved

| Role | Path |
|---|---|
| Orchestrator instructions | `prompts/optimize.prompt` |
| Small-scale smoke test | `prompts/test_optimize.prompt` |
| Runner script | `scripts/run_optimize.py` |
| Baseline prompt (the thing being optimized) | `src/dynamic_harness/core/agent_system_prompt.txt` |
| Model/provider config | `harness.json` |
| Runtime output (artifacts/commits/traces) | `.dynamic-harness/` |
| Benchmark output files | `.optimize_benchmarks/` |

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

Clean the benchmark state, then run the script (edit
`scripts/run_optimize.py` if you want the small test instead of the full run):

```bash
rm -rf .optimize_benchmarks/*
source venv/bin/activate
python scripts/run_optimize.py
```

- The script reads `prompts/optimize.prompt`, creates a Runtime, injects the
  configured LLM, and runs the orchestrator.
- Live output prints each delegation and tool call; the final `=== RESULTS ===`
  block summarizes the best prompt, artifact IDs, agent/token/commit counts,
  and total time.
- Expect **5–10 minutes** and roughly **2M tokens** for the full 36-run run
  (the observed run: 39 agents, 2.1M tokens, ~423s).

> The runner deliberately calls `trace_store.clear()` before each run to avoid
> stale trace data. Benchmark files persist under `.optimize_benchmarks/`.

### Running just the small test

To sanity-check the pipeline quickly, point the script at the smoke test:
`scripts/run_optimize.py:83` reads `prompts/optimize.prompt`; temporarily
change it to `prompts/test_optimize.prompt` (single task, 3 prompts), or run
the CLI directly:

```bash
source venv/bin/activate
dynamic-harness -m prompts/test_optimize.prompt
```

## 5. Outputs

After a full run, `.optimize_benchmarks/` contains:

| File | Contents |
|---|---|
| `variants.txt` | 5 variant prompts from Round 1 |
| `evaluation_round1.txt` | Ranking of all 6 Round-1 prompts (1 = best) |
| `variants_round2.txt` | 3 refined variants from Round 2 |
| `evaluation_round2.txt` | Final ranking of the 6 Round-2 prompts |
| `best_prompt.txt` | **The single best system prompt (complete text)** |
| `largest_files.txt`, `fibonacci.py`, `test_fibonacci.py`, `todos.txt` | Benchmark task outputs |

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

Edit `prompts/optimize.prompt` to change the three benchmark tasks or the
variant-generation guidance. The tasks are intentionally simple and
self-verifying (write output to disk, then `report()` it), so the evaluator can
compare correctness across prompts: large-file discovery, fibonacci
code-gen + assert tests, and recursive TODO/FIXME scanning.
