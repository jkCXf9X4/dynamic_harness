# Investigation — a cheap, robust watchdog for the harness runtime

Status: Investigation (findings only, no code change). Source: backlog hang/timeout items ("hangs at a `tool_result`", "bash commands not completing and killing agents", "main orchestrator still times out", "sub-orchestrators must not time out"), the comms deadlock (`../../04-verification/communication-structures/FINDINGS.md`), and a review of the current safety layers.

## 1. What a watchdog must protect against (threat model)

| # | Threat | Mechanism in this codebase | Observed? |
|---|--------|---------------------------|-----------|
| T1 | Agent stuck on a tool with no internal bound | `Agent._run_loop` executes `ToolRegistry.execute` (core/agent.py:1213) with **no run-level `wait_for`**. Every tool self-limits, but each limit is bypassable: `bash` accepts an arbitrary `timeout`; a custom tool may not bound at all; a tool that catches `CancelledError` defeats every asyncio deadline. | Backlog "hangs at `"name":"bash"` … `(no output)`" |
| T2 | Circular blocking `converse` (lock cycle) | `converse` → `continue_with_input` → target `_run_guarded()` acquires `_loop_lock`. An A→B→A cycle suspends both loops awaiting tool calls; iteration/loop guards never fire (the loop is not iterating). | Confirmed in comms battery (FINDINGS.md "Deadlock: circular `converse` blocks the whole tree") |
| T3 | Root / sub-orchestrator exempt from its own run budget | `safety.disable_root_timeout: true` + streaming children mean **top agents never time out internally** by design; an external boundary must exist. | Backlog: "main orchestrator still times out" / "ensure sub-orchestrators cannot time out" |
| T4 | Event-loop wedge (sync/blocking call in the loop thread) | No watchdog helps if `wait_for` cannot advance — third-party sync calls, a blocking callback, or a swallowed task deadlock stop all progress while `wait_for` calmly waits. | Not yet observed; structural weakness |
| T5 | Process freeze / orphaned subprocess | A truly wedged host (C-extension deadlock, kernel sleep, hung pager inheriting the terminal) survives every asyncio layer; needs OS-level supervision. | Not observed; standard ops risk |

## 2. Current defences (layered, per-agent)

| Layer | Where | Bounds |
|-------|-------|--------|
| Per-call LLM deadline | agent.py:893–900 + `llm.call_timeout_seconds` (500s) in `OpenAIProvider` | a single request (asyncio `wait_for` + httpx) |
| Per-run wall clock | `_call_llm_with_run_budget` agent.py:958–999, `TimeoutPolicy`, `safety.timeout_seconds` (7200s) | **LLM calls only**; root exempt by default |
| Iteration cap + loop guard | `safety.max_iterations` (400), repeated-call / near-identical detection | counting turns; silent while suspended in a tool |
| Per-tool bounds | bash `timeout` (120s) + `killpg` on timeout/cancel (core/tools/process.py:103–116); webfetch httpx 30s; result_bash `wait_for` | per-op, agent-suppliable |
| Whole-run wrapper (*benchmark only*) | `run_comms.py:162` `asyncio.wait_for(run_one(...), timeout=per_run_timeout_s)` | cancels the whole run; **not wired into CLI / `Runtime.run`** |

Net effect: the only existing "watchdog" is the comms benchmark; all production paths (CLI `Runtime.run`, `api/harness.py`) can still hang on T1–T4.

## 3. The three cheap gaps (correctness fixes, not architecture)

1. **Bound tool execution by the run budget.** Wrap `ToolRegistry.execute` (agent.py:1213) in `asyncio.wait_for(...)` at `max(remaining_run_budget, min_tool_floor)` — identical to the LLM path; reuses `TimeoutPolicy.remaining_seconds`. Closes T1 for every tool (bash's arbitrary `timeout`, unruly custom tools, no bound at all) with a few lines. Also clamp bash's default when no explicit `timeout` given.
2. **Whole-run guard in the production path.** Mirror `run_comms`' proven pattern into `Runtime.run` / CLI: wrap `await root.run()` with `asyncio.wait_for` under a distinct `watchdog` knob. Because it is **external to the agent**, it covers the root-exempt case (T3) for free. Cancellation works for T1/T2 (bash re-raises `CancelledError` after `killpg`; `continue_with_input` eventually hits a cancellable yield, releasing the lock chain via `finally`).
3. **Documented external-supervision contract** for unsupervised/live-capital runs (T5): shell `timeout --kill-after=` / systemd `WatchdogSec=` / heartbeat file. Outside the library; a runbook contract, not code.

These three alone convert today's "can hang forever" into "bounded at the whole-run level" — the same guarantee the comms battery already enjoyed.

## 4. Watchdog designs, cheap → robust

| Design | Mechanism | Catches | Cost | Robustness / failure mode |
|--------|-----------|---------|------|---------------------------|
| W1 — hidden whole-run `wait_for` (§3.2) | one asyncio deadline around the root coroutine | T1*, T2, T3 | ~zero (one wrapper) | **Depends on a live loop**: a wedged loop (T4) means the deadline never fires; a tool swallowing cancellation means `wait_for` itself hangs |
| W2 — activity-heartbeat monitor (coroutine) | runtime task ticks every N s; compares `last_progress_ts` (bumped once per completed LLM/tool result) vs `watchdog.no_progress_seconds`; on expiry fails the offending agents/subtree with a distinct `status` | T1–T3 with sub-agent attribution | tiny: 1 coroutine + 2 `monotonic` writes per result | Still a coroutine — dies with a wedged loop (T4 untouchable); needs the window to exceed the longest *legitimate* single op |
| W3 — loop-liveness probe in a monitor thread | daemon `threading.Thread`: every tick does `loop.call_soon_threadsafe` to stamp a liveness counter **and** reads the progress counter; both stalled → dump DAG/progress to trace, then hard `os._exit(status)` | everything above **plus T4** | one thread + one `call_soon_threadsafe` per tick | The thread is independent of the loop — survives what the loop cannot; gives up gracefully-ish (best-effort trace, then exit) because a wedged loop cannot be cancelled |
| W5 — external supervisor | `timeout` / systemd `WatchdogSec` / heartbeat-file watcher outside the process | T5 and everything else (kills whole process) | zero in-process; needs deployment | Most robust, least informative (whole-process, no per-agent attribution unless it reads the trace) |

Key structuring decision: **one runtime-level watchdog, not one per agent.** N agents × tick multiply cost for no benefit (the tree stalls as a unit in T1–T3), and per-agent isolation already exists via the `status`/`kill`/`resume` tools + streaming. Per-agent attribution is achieved by *recording which agent was last active* (a `last_progress_ts` per agent, stamped only on that agent's results) — cheap columns, not extra processes. Only the L1 tool bound (which already routes through per-agent budgets) stays per-agent.

## 5. Recommended composition ("cheap **and** robust")

Adopt **§3.1 + §3.2** (the two cheap gaps) as the baseline, then **W3** (monitor thread + progress/liveness heartbeat) as the actual watchdog:

1. L1 tool-bound closes T1 inside the run.
2. W1 whole-run guard closes T2/T3 with a configurable `watchdog.timeout_seconds` (default reuse of `safety.timeout_seconds`, since the root is exempt).
3. W3 monitor thread: inactivity of `watchdog.no_progress_seconds` (default, e.g. 3× the longest expected op, or 900s like the battery) → fail the silent agents with `status=watchdog_timeout` (distinct from `safety.timeout_seconds` so parents can distinguish and resume) — then, if even the loop-liveness probe is dead, write diagnostics + `os._exit(2)`.
4. W5 external contract documented for production (runbook) — the only layer with no in-process failure modes.

Ordering is intentional: each layer costs little alone; together they cover the whole threat table, and each falls back to a stronger, cheaper-captured layer (asyncio → thread → OS) as the failure gets more severe.

## 6. Diagnostic hygiene (echoes the "trace send/receive" backlog item)

Every watchdog verdict must land in the existing event streams — `events.jsonl`, comms trace, activity events — with the agent ids involved and a monotonic since-last-activity figure. Rationale: the backlog's hang was diagnosed by grepping a `trace.jsonl` entry; a watchdog that fires but does not say *which agent, on which tool, silent for how long* just trades a hang for a mystery.

## 7. Verification sketches (for the eventual task contract)

All deterministic with the existing mock-LLM test approach:

- **T1:** a mock/tool that awaits `asyncio.sleep(forever)`; assert the run fails via the tool bound and reports a distinct watchdog/tool-timeout failure.
- **T2:** two mock agents whose `converse` answer each other's `continue_with_input` (reuse the FINDINGS.md lock-graph fixture); assert the whole-run guard cancels and records `timed_out` instead of hanging.
- **T3:** root with `disable_root_timeout: true` and a mock LLM that stalls; assert the W1/W3 boundary (not the internal budget) fires.
- **T4 (W3 only):** monkeypatch a tool to block the loop thread synchronously; assert the monitor thread still fires the liveness probe (and the process exits, under a subprocess test) rather than hanging pytest.

## 8. Recommendation

Proceed as an IMP under the roadmap's controlled-change register: a `watchdog.*` config section, §3.1 + §3.2 now (both ~10-line, low-blast-radius), W3 as the centerpiece, W5 as a documented runbook contract. Resolution for the roadmap register: this subsumes — and should reference — IMP-015's fallback-loop theme (an idle watchdog and a looping agent are different diagnoses of the same "no forward progress" signal) and the backlog hang/timeout items listed at the top.
