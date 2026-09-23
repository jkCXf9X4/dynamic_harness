# Investigation — W3 utilization: what the monitor-thread watchdog can actually do

Status: Investigation (follows `watchdog.md`; no code change. Scope: the design
surface of W3 — the daemon monitor thread + `call_soon_threadsafe` liveness probe —
and the concrete ways to utilize it. Part of the W1→W5 cascade
(see `watchdog.md` §5 for where it sits: L1 tool-bound → W1 whole-run guard →
**W3** → W5 external supervisor.)

## 1. The structural property that defines the design space

W3 is the only component in the system that can act when the event loop cannot. Every
other mechanism (policies, nudge injections, kill/status/resume tools, cancellation,
self-heal) lives inside the loop and dies with a wedged loop. W3 sits in its own
thread and watches two independent signals:

- **Progress** — per-agent `last_progress_ts` (stamped once per completed LLM/tool
  result, per agent; zero cost beyond two `monotonic()` writes per result).
- **Loop liveness** — every tick the thread does `loop.call_soon_threadsafe` to stamp a
  counter; if the counter stops advancing while progress is also stale → the loop
  itself is wedged (T4) and in-loop actions are futile.

Utilization = deciding what that switch does in each failure class, and with what
cost/blast-radius. All utilization options below are just different behaviors of the
same thread; they compose into an escalation ladder, not alternatives.

## 2. The utilization axes

| Axis | Choices |
|------|---------|
| A. Detection scope | progress-only · progress + loop-liveness · absolute wall-clock · composite levels |
| B. Action repertoire | observe · nudge-inject · fail agents · cancel run · subprocess sweep · checkpoint-then-exit · re-exec-resume · signal escalation |
| C. Firing policy | single-shot vs staged escalation · per-agent vs whole-run attribution · graceful-first (in-loop actions first; terminate only when loop dead or grace exhausted) |
| D. Integration | armed/disarmed by `Runtime.run`/CLI around the root await (start, stop in `finally`); stamp sites = the two yield points + child-settle; new `watchdog.*` config section parallel to `safety.*` (external vs loop-internal) |
| E. Diagnostics | per-agent silent-duration table · whole-tree DAG · `threading.enumerate()` + `sys._current_frames()` stacks · last trace/comms pointer · `<run_root>/watchdog_report.txt` + events.jsonl + distinct exit code |
| F. Lifecycle | arm per root-run segment; disarm in `finally`; per-run watchdog object (no pool) so programmatic multi-run callers stay clean |

## 3. Concrete ways to utilize — menu

| # | Utilization | What it does | Catches | Cost | Blast radius | Conflicts / cautions |
|---|--------------|-------------|---------|------|--------------|---------------------|
| U1 | **Observe-only diagnosis** (`mode: observe`) | thread only *records*: silent-agent table, loop-liveness, thread stacks → `watchdog_report.txt` + `events.jsonl`; never touches the run | every class, **diagnosable** | ~a thread + tick | none | start here; zero-risk and pays for itself in the T4 stack dump alone (a wedged loop has no other way to report what it was doing) |
| U2 | **Watchdog-nudge inject** (recover-in-place) | loop alive + agent silent past `no_progress_seconds` → inject `[watchdog] … no progress in Ns (last result: <tool>)…` so the agent can unwedge itself, budgeted like `repeated_recovery_attempts` | T1,T2 (self-unwedging) | one `call_soon_threadsafe` | prompt-level only | exclude legitimately-waiting states (parent awaiting children / blocking `converse` — attribute to the *deepest* silent agent, not its waiting parent); advisory only, never instant-fail |
| U3 | **Fail with attribution** (`watchdog_timeout`) | nudge exhausted → mark the deepest silent agent failed with a distinct status; parent's `stream_children` settle event lets it react via existing `resume`/`kill`/re-delegate (heal machinery reused, nothing new added) | T1 with a genuine stuck child, T2 | one in-loop fail call | subtree (that agent + its silent children), recovered by parent | requires loop alive; per-agent, never the waiting parent; exempt from auto-heal exactly like `safety.timeout_seconds` (parent decides) |
| U4 | **Run-cancel with attribution** | loop alive + no progress anywhere past window → cancel the whole root run task (`call_soon_threadsafe(run_task.cancel)`) under a `watchdog` status; mirrors W1's `wait_for` but fires on *no-progress* instead of only wall-clock | T1,T2,T3 (whole-run backstop, root-exempt included) | near-zero (one cancel) | whole run | less surgical than U3; prefer U3 when a culprit is identifiable; cancellation is safe — bash re-raises `CancelledError` after `killpg`, lock chains release via `finally` |
| U5 | **Subprocess sweep** (orphan reaping) | thread tracks live bash/result_bash process-group pids (stamped at spawn, cleared at reap); on stale progress + liveness-alive, `killpg` any group whose op exceeded a generous per-op ceiling — independent of the agent-suppliable bash `timeout` | T1 (agent passed huge `timeout`), cancelled-runs with lost in-loop cleanup | a dict of pids + one sweep per tick | kills only harness-owned groups (never user processes) | per-op ceiling must exceed any *legitimate* op or a long `pytest` gets killed; pids map is thread-safe bookkeeping |
| U6 | **Wedged-loop hard-exit** | liveness probe dead (no task completes past `loop_dead_seconds`) + progress stale → stop in-loop attempts; write diagnostics (stacks, DAG, silent table); then `os._exit(exit_code)` | **T4, T5** — the only utilization robust to a dead loop; turns a hang-forever process into a bounded, diagnosable exit code the external supervisor (W5) can see and restart | one exit + diagnostics write | whole process | gate by *both*-stalled signal only (never on progress-stall alone while the loop is alive); exit code distinct per class (`watchdog` vs normal timeout) for scriptability; traces are event-appended so most state survives |
| U7 | **Self-restart / re-exec resume** | same trigger as U6 but instead of dying: `os.execv` the same interpreter with `--resume <root_id>` — checkpoints persist per committed turn (agent.py `_run_loop` → `CheckpointStore`), so the run continues from the last committed turn, not from scratch | T4,T5 with cheap recovery (no supervisor needed) | one execv | process replaced; keeps supervisor port | the re-exec must be prepared at arm-time (argv snapshot, resume id, session/env; fallback to U6 exit if re-exec setup unavailable; loop-dead verdict is rare enough that a bounded restart is the right default |
| U8 | **Signal escalation (hard)** | after U6/U7 preparation: `SIGTERM` to self → grace → `SIGKILL`/`os._exit`; optional SIGTERM to a stray bash pgid discovered by U5 | T5 (process wedged beyond `os._exit` reach, e.g. C-extension deadlock) | one signal | whole process | last rung; mostly a stub for W5's benefit — a genuinely wedged process may not even run the thread |

## 4. Recommended utilization (composition, not choice)

Arm as a **staged escalation ladder**, each stage its own window, graceful-first:

1. **U1 observe** — always on (it is free); every stage below *also* writes its verdict through U1's channel (so diagnostics are complete even when a later stage fires)।
2. **U2 nudge** — `no_progress_seconds` past last result (advisory, budgeted, deepest-agent-attributed); excludes legit wait states)。
3. **U3 fail-with-attribution** — nudge budget exhausted, loop alive (deepest silent agent → `watchdog_timeout`; parent reacts with existing resume/kill tools)。
4. **U4 run-cancel** — fallback when no single culprit identifies (whole-run `watchdog` verdict)。
5. **U5 subprocess sweep** — continuous side-channel; independent per-op ceiling (huge-timeout bash, orphaned groups)。
6. **U6/U7 loop-dead** — both-signals-stalled → diagnostics then exit/re-exec (the distinctive W3 role; config default: **re-exec-resume** (U7) when preparable, else exit (U6))。
7. **U8 signal** — last rung, mostly delegating to W5。



Config shape (new `watchdog.*` section in `harness.json`, parallel to `safety.*` — one
is loop-internal, one is external):

```jsonc
"watchdog": {
  "enabled": true,
  "tick_seconds": 2.0,
  "no_progress_seconds": 120.0,     // U2/U3/U4 window
  "nudge_attempts": 2,                // U2 budget (mirrors repeated_recovery_attempts)
  "loop_dead_seconds": 30.0,         // U6/U7 window (liveness dead)
  "max_total_seconds": null,              // absolute arm (external whole-run backstop)
  "per_op_ceiling_seconds": 600.0,     // U5 sweep ceiling
  "mode": "intervene",                     // observe | nudge | intervene | resurrect
  "exit_code": 73,                        // distinct from normal timeout codes
  "report_path": "<run_root>/watchdog_report.txt"
}
```

Semantics: `mode` picks the deepest stage armed(`observe`=U1;`nudge`=+U2;
`intervene`=+U3..U6;`resurrect`=+U7;hard signal (U8) is always the last rung
and mostly defers to W5). `no_progress_seconds` must exceed the longest *legitimate* single
op (a long test suite, a long fetch) or U5's per-op ceiling and U2/U3 windows
false-positive; defaults aim 2–3× the longest expected op rather than reusing
`safety.timeout_seconds`(which is a whole-context budget, not an op window)。

## 5. Interplay with existing mechanics (reuse, don't duplicate)

- **Attribution leverages stream_children**: marking the *deepest* silent agent failed pushes a settle event to its parent — the watchdog needs no new event channel; existing `resume`/`kill`/`status` tools handle the reaction。
- **Self-heal exemption**: `watchdog_timeout` must be exempt from automatic self-heal, exactly like `safety.timeout_seconds` — a watchdog verdict implies something fundamentally stuck;the parent decides (resume blunt vs fresh vs re-delegate)。 If `resurrect` mode re-execs, recovery is checkpoint-based (`Runtime.resume(agent_id)`), not auto-heal-based。
- **`safety` vs `watchdog` split**: `safety.timeout_seconds` stays the loop-internal per-agent budget; `watchdog.max_total_seconds` is the external whole-run backstop — together they cover T3's root-exemption without contradicting `disable_root_timeout` (internal per-agent cap off; external run boundary on)。
- **Interactive REPL**: arm per root-run segment (start/stop in `finally`); disarmed between continuations so an idle prompt never trips no-progress。
- **Comms deadlock (T2)**: during a circular `converse`, progress is stale *everywhere* — U4 (whole-run) and U2's deepest-agent nudge both fire;U3 should not fail only one participant of a lock cycle (the whole ring is stuck); prefer U4 for T2, and a `converse`-await state should be treated as a legit wait for attribution (deepest-silent = the innermost agent of the ring, which the parent-of-parent chain already covers)。

## 6. Verification sketches (deterministic, mock-LLM)

- **U1/U2:** mock tool that sleeps; assert `watchdog_report.txt` lists the silent agent with duration, and a nudge user-message appears after `no_progress_seconds` (use tiny windows)。
- **U3:** mock tool sleeping past nudge budget; assert deepest agent ends `watchdog_timeout` and the parent's settle path reports it (status tool / stream settle), no auto-heal fires。

- **U4:** two mock agents in the FINDINGS.md lock-graph fixture;assert whole-run `watchdog` verdict (not hang) with the lock cycle attributed。
- **U5:** bash tool invoked with huge `timeout`; assert killpg fires at `per_op_ceiling_seconds` (subprocess test: process group reaped)。
- **U6/U7:** monkeypatch a tool to block the loop thread synchronously;run the harness in a subprocess; assert the watchdog exits with `exit_code` (or re-execs the same run and completes from checkpoint), not a hung pytest。

## 7. Recommendation

W3's value is not "a new timeout" — it is the **external switch that keeps working when
the loop can't**, plus a diagnostics channel that makes every other failure class
examinable. Utilization should be a configurable staged ladder (U1 always, U2/U3/U4/U5
in `intervene` mode, U6/U7 as the loop-dead rung, U8/U5-external as the last
resort), with the deepest-agent attribution reusing stream_children/heal tools instead of
new machinery. Track as an IMP under `06-evolution/roadmap.md` (referencing this + `watchdog.md`),
starting with `mode: observe` (U1) to validate the signals against real hangs before
arming intervention—— precisely the discipline the repo's own controlled-change rule demands。