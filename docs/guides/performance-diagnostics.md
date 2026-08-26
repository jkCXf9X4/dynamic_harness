# Performance Diagnostics — How to Find the Slowdown

Agent contexts are supposed to stay "contained", yet wall-clock time grows far
faster than linear as **conversation length** and **agent count** rise. Most of
that remaining growth is *bookkeeping overhead* in the runtime/CLI, not LLM
prompting — and — critically — a large chunk of it is **not actually bounded by
`active_turn_window`** (see hypothesis H1). This guide is the methodology for
narrowing it down, plus an empirically-built scaler tool to run first.

## 0. Run the built-in scaler first

```
python -m dynamic_harness.benchmark.profile_scaling            # full grid
python -m dynamic_harness.benchmark.profile_scaling --quick   # fast sanity pass
```

It uses a **mock LLM (no network)** and measures, in isolation, the scaling of
each suspected hot path. Read the *shading* column: a ratio that roughly doubles
when size doubles = **superlinear = suspect**. The tool now prints four axes:

| Section | Question it answers | Dominant axis |
|---------|--------------------|---------------|
| A  | Does `persist_checkpoint()` cost grow with conversation length? | turns |
| A2 | How many **bytes/tokens are actually SENT to the LLM** per turn? | turns |
| B  | Does `Repository.commit()` (full journal rewrite) grow with agent count? | agents |
| C  | Does the CLI snapshot (`StateWriter.snapshot`) grow with agent count? | agents agg. |
| D  | End-to-end `Agent.run()` wall time at growing turn counts | end-to-end |

If the box this app runs in is CLI/REPL, C is usually the biggest "why did it get
so much slower than I expected". If it is the programmatic `Runtime` API, A2 and A
dominate over long conversations.

## 1. Two axes, two root causes (already localized)

### H1 — The prompt sent to the LLM is NOT bounded (conversation-length axis)

`AgentContext.active_turn_window` (default 50) is often read as "only the last 50
turns reach the model". **It does not.** It only limits which turns are *listed*
in the Context Observation for pruning:

- `context.active_turn_ids()` → `context.py:120` → trims the *listing* in
  `build_observation` → `prompts.py:148`.
- The actual request sends the **entire** message history unchanged:
  `sent = list(self.context.messages)` → `agent.py:1168`, committed turn after
  turn by `commit_turn` → `context.py:58`.

So unless the model happens to call `prune`/`compress` (manual tools), every turn
re-sends a longer prompt → proportionally more transfer + prefill per call, and
superlinear total wall time. The scaler A2 shows this directly (≈8x payload at
800 turns). **Contained-context is an assumption, not an invariant.**

### H2 — CLI snapshot rebuilds the whole tree on every terminal event (agent-count axis)

Each report/failure/escalation routes to `StateWriter.snapshot()` → `state.py:84`
which called `build_agent_tree(runtime)` **twice** → `state.py:54,60`. Per node it
called `runtime.provenance()`, and `provenance()` did
`repository.log(limit=1_000_000)` → **sorts every commit**, per node →
`runtime.py:796` / `repository.py:110`. As agents accumulate this becomes roughly
O(agents · commits log commits) *per event*, and there is one event per agent →
compounding. The scaler C showed ≈117x at 320 agents.

**Status: fixed.** `snapshot()` now builds the tree once (`state.py:51`),
`build_agent_tree()` resolves provenance through a single-pass index
(`runtime.provenance_index()`, `runtime.py:825`) plus a cheap per-node `stat` for
the trace path, and `Repository.all_commits()` (`repository.py:113`) avoids a
per-node sort. Section C of the scaler is now linear→sublinear
(≈18x at 320 agents, below the 32x linear baseline) at single-digit ms. Purely
local CPU/disk — no LLM/cache interaction.

## 2. Checklist for a live (LLM) run — attribution before guesswork

1. **Reproduce on a fixed, small task**, then scale one variable (turns OR
   children) and watch total wall time go superlinear. Keep LLM the same.
2. **Confirm H1** by watching the `ITERATION` activity events: the `prompt_tokens`
   field (agent.py:702) should be ~constant if context is truly bounded; if it
   climbs with `turn`, H1 is in play.
3. **Confirm H2** by strace/measuring `agent_tree.json` / `stats.json` /
   `commits.jsonl` growth, or just add a timestamp around `writer.snapshot()`.
4. **Profile CPU hotspots** with cProfile against a mock-LLM run (no network
   noise) so the profile reflects app code, not the provider:
   ```
   python -m cProfile -o /tmp/prof.out -m dynamic_harness.benchmark.profile_scaling --quick
   python -m pstats /tmp/prof.out   # 'sort cumtime'; 'stats 20'
   ```
   Frequent offenders: `persist_checkpoint`/`model_dump_json`, `Repository._flush`,
   `SequenceMatcher` (near-identical detection, agent.py:889), `provenance`/`log`.
5. **Check the trace** (JSONL per agent) for long in-flight gaps that point at the
   provider vs the app: `record_llm_request` → `record_llm_response` latency is
   provider+prefill; everything else is local.

## 3. Which axes matter for your deployment

- **Programmatic `Runtime` API, few agents, long conversations** → H1 first
  (auto-bound the sent prompt, or nudge/force prune; verify `prompt_tokens`
  flattens).
- **CLI / REPL, many short-lived agents** → H2 first (build the tree once per
  event, stop re-sorting all commits per node — sort once, or index by agent id).
  **Done** — see H2 status above; re-run the scaler to confirm it stays flat.

## 4. Interpret the scaler honestly

- The scaler's absolute ms are **small** (they isolate one function). A
  superlinear *shape* is the signal, not the size — multiply by how often the
  path runs in real use.
- `persist_checkpoint` and `Repository._flush` both show superlinear shapes but
  tiny constants; they matter at scale or on slow disks, not on the first run.
- A2 and C are the ones that "move the needle" in honest productions: A2 because
  it hits the *model* latency every turn, C because it hits every terminal event.

## 5. Repeatable protocol (when you fix something)

1. Before/after each change, run the same scaler command and the same live task.
2. Record: total wall time, the two smoked-out axes' ratios, and `prompt_tokens`
   at the final turn.
3. A fix is only a win if the relevant ratio stops climbing *and* the live run
   gets faster; keep the scaler run committed to the PR for a before/after.

## 6. Live-run profiling (for bug reports / hand-off to a developer)

The scaler is a synthetic micro-benchmark. When you want to capture what a *real,
live* run actually did — including real LLM latency, event handling, and CLI
overheads — re-run the exact failing scenario under the live profiler and send
the artifacts back:

```
dynamic-harness --profile "your real prompt..."        # batch
dynamic-harness --profile -i                            # whole interactive session
dynamic-harness --profile --profile-dir /path/to/out ...  # control output location
```

On exit (batch) or when you quit the REPL, it writes under `<run root>/profile/`
(or `--profile-dir`):

- `profile.txt` — human-readable top-40 table (sorted by self-time), plus
  environment/version metadata at the top.
- `profile.json` — machine-readable per-function aggregate counts
  (`top_of_stack`, `on_stack`) + run metadata; easy to paste directly into an
  issue or a script.
- `meta.json` — captured environment: package version, Python, platform, argv,
  model, interactive-mode flag. Include it so the developer can reproduce the
  stack.

Notes:
- Profiling uses a **sampling** timer (default 10 ms) that grabs the running
  stack on the main thread each tick — NOT cProfile's deterministic tracer.
  Overhead is therefore roughly constant (~one stack walk per interval),
  regardless of how many function calls the LLM/tool loop makes, which is what
  keeps `--profile` cheap. A hot path shows up as a *sample count*, not
  millisecond timings.
- It captures the real session exactly as run, so prefer reproducing the actual
  (slow) task over a toy prompt.
