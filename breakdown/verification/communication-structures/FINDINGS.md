# Findings — real-LLM communication comparison (P4)

Status of each probe is appended LIVE under `## Probe log`; full metric tables
are produced by `python -m dynamic_harness.benchmark.run_comms` into
`RESULTS.md` / `metrics-cells.json`.

## Deadlock: circular `converse` blocks the whole tree — CONFIRMED

Reproduced with the real LLM (deepseek-v4-flash via OpenRouter proxy) on the
`off` cell, interdependent collab task, 5 agents (root + 4 children):

```
07:53:01 root   converse(5e3ccf522729)   "Final step: child1 ..."
07:53:39 5e3c   converse(bd3aedad782f)   "Please send me your x1 value via converse"
07:53:46 bd3a   converse(5e3ccf522729)   "x1=3"
```

After that, **zero** new LLM calls across all five trace files while the
process idled (traces: `*_ws_2bj7m6yn/traces/*`). Mechanism:

- `converse` (layer-off path) → `ToolContext.continue_with_input` →
  `Agent.continue_with_input`, which **acquires the target's `_loop_lock`** and
  runs `_run_guarded()` to completion (an entire re-run of the target).
- A converse executed *inside* the caller's own loop (so the caller holds its
  own lock — directly or via the run loop) while target and caller each await
  the other's `continue_with_input` ⇒ **circular lock wait**.
- The agent-level wall-clock/safety guards do not fire: the loop is suspended
  awaiting a tool call, not iterating.

Observations:

1. The same risk exists on the comms layer: `deliver_comms_message`
   (the routed `converse` path) also calls blocking `continue_with_input`.
   Only `message` (`submit_input`, fire-and-forget queue) and
   `post`/`channel_read` (log + watermark) are non-blocking — so channel-based
   topologies are robust to this; any topology where the model is tempted to
   `converse` in a cycle can deadlock.
2. The lock graph on the failing run was: root → 5e3c → bd3a → 5e3c (cycle).

Mitigation for the battery:

- `run_comms` now carries a per-run watchdog (`--timeout-s`, default 1200)
  that cancels a deadlocked run and records it as `status: timed_out` instead
  of hanging the process.
- The `off` baseline is expected to be the worst case here (no channels → the
  only peer-sharing tools are `converse`/`message`).

Not fixed in this pass: making `converse` bounded / lock-safe is a runtime
design change (e.g. bounded wait for the target's next assistant message
instead of the target's whole re-run), deliberately out of scope for the bed.

## Probe log — real-LLM battery, 2026-09-18 (deepseek/deepseek-v4-flash-0731 via OpenRouter)

Single replicate of the interdependent collab task (4 children must share
neighbor integers; verifier is mechanical). Watchdog 900s/run.

| cell | status | correct | turns | agents | tokens | latency s |
|------|--------|--------:|------:|-------:|-------:|----------:|
| off | timed_out | — | 0 | 1 | 0 | 900.0 |
| shared | completed | True | 40 | 7 | 799,955 | 389.3 |
| topics_parent | completed | True | 232 | 6 | 5,219,622 | 764.5 |

Readings:

1. **off deadlocks again** — the root's chain of blocking `converse` calls hit
   the 900s watchdog with zero turns committed. Consistent with the deadlock
   reproduced above: no channels ⇒ agents coordinate by blocking RPC ⇒ cycle
   risk every time. (This run never even completed a single turn.)
2. **shared wins decisively**: one channel, agents post + `channel_read`
   (non-blocking), correct in 40 turns / 389s. This is the cell where the
   "shared log" matches the collaboration pattern.
3. **topics_parent also completes correctly but with ~6× the churn** (232 turns,
   5.2M tokens, 765s). Hypothesis to test next: the parent-declared channel set
   (`findings`) plus per-topic watermarks pushed agents into more verification /
   topic-policing back-and-forth, or repeated `channel_read` polling; a bigger
   replicate budget + per-tool turn breakdown (from the traces) would separate
   "LLM verbosity" from "harness overhead".

Caveat: n=1 per cell, pricing unconfigured (cost $0), and the run was
interrupted once by my own kill — treat the ratios, not the absolutes, as signal.