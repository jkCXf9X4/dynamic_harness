# Live Diagnosis & Deployment Axes

## Checklist for a Live (LLM) Run — Attribution Before Guesswork

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

## Which Axes Matter for Your Deployment

- **Programmatic `Runtime` API, few agents, long conversations** → H1 first
  (auto-bound the sent prompt, or nudge/force prune; verify `prompt_tokens`
  flattens).
- **CLI / REPL, many short-lived agents** → H2 first (build the tree once per
  event, stop re-sorting all commits per node — sort once, or index by agent id).
  **Done** — see [root-causes.md](root-causes.md); re-run the scaler to confirm
  it stays flat.

## Interpret the Scaler Honestly

- The scaler's absolute ms are **small** (they isolate one function). A
  superlinear *shape* is the signal, not the size — multiply by how often the
  path runs in real use.
- `persist_checkpoint` and `Repository._flush` both show superlinear shapes but
  tiny constants; they matter at scale or on slow disks, not on the first run.
- A2 and C are the ones that "move the needle" in honest productions: A2 because
  it hits the *model* latency every turn, C because it hits every terminal event.
