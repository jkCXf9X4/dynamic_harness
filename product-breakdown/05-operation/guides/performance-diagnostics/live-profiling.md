# Live-Run Profiling

The scaler is a synthetic micro-benchmark. To capture what a *real, live* run
actually did — real LLM latency, event handling, CLI overheads — re-run the
exact failing scenario under the live profiler and send the artifacts back:

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
