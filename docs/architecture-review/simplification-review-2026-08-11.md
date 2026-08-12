# Architecture Review — Simplification & Ease of Development (2026-08-11)

> Critical look at the *overall* architecture with one lens: **what makes this
> harder to develop than it needs to be, and what alternatives would simplify
> it.** This complements the correctness/boundary review (see
> `review-2026-08-11.md`, whose §1–§7 fixes are applied). It deliberately
> challenges some of the project's own architectural weight rather than just
> patching around it. Experimental software — breaking changes are fine.

---

## 1. Where the architecture actually is (post-fix, ~5,400 LOC)

```
api/Harness ──► AgentRunner ──► Runtime ──► Agent (run loop) ──► ToolRegistry ──► ToolContext ──► 17 tools
                                    │
                                    ├─ ArtifactStore (artifact.json per task)   ── persistence A
                                    ├─ Repository   (sharded commit.json, DAG)  ── persistence B
                                    ├─ EventBus (9 activity event types)
                                    ├─ UsageTracker / TraceStore (JSONL)
                                    └─ path/repo/usage locks

UI layer    : cli/terminal (Rich)       cli/tui (Textual)       ← present.py (view-models) + render.py
Programmatic: api/Harness
Prompting   : agent_system_prompt.txt + Agent.environment_info + context_observation + task/role assemble
Benchmark   : tasks, runner (os.chdir), metrics, scoring, report, run
```

**Verdict up front:** the core (agent loop + schema-driven tool dispatch + runtime
orchestration + artifact handoff) is proportionate and good. The weight that hurts
development lives in the *supporting* layers: **three run entry points, two
persistence stores, heavy context-management machinery, a dual-UI render stack,
prompt assembly scattered across 4 places, and a benchmark that mutates global
`os.chdir`**. Each is individually defensible; together they raise the cost of
every change and the mental model a new dev must hold.

---

## 2. Complexity hotspots (ranked by toll on development)

### H1. Three independent ways to run an agent
`Agent.run()` (`core/agent.py:145`), `AgentRunner.run()` (`core/runner.py:21`),
and `Harness.run()/run_async()` (`api/harness.py:152`). `AgentRunner` is now a
~40-line shim that only reads `root.outcome` and maintains a redundant `events`
list (unused by the TUI, which is event-bus-driven). `Harness` wraps the runner.
The benchmark, tests, CLI all use slightly different combinations.

**Cost:** a new contributor must pick one; three copies of "delegate + run +
read outcome" logic exist. `AgentRunner` adds next to nothing today.

### H2. Context management is the most intricate code in the repo
`core/context.py` (342 LOC) implements committed turns + **prune/restore** with:
`prune_markers` plus positional-index bookkeeping that must be *re-fixed on every
restore* (`restore()` shifts downstream marker indices), in-flight-prune
(deferring a prune to the next committed turn), retention caps with eviction, and
token estimates. Every one of these has subtle ordering invariants, and they are
covered by the most fragile tests in the suite (positional marker assertions).

**Cost:** highest-cognitive-load module; high risk on any touch; and the *marker
at an exact position so restore re-inserts in place* behavior is rarely what an
LLM needs — `restore(prune_id)` could almost always re-append at the end.

### H3. Two persistence stores with overlapping jobs
- `ArtifactStore` → `root/<artifact_id>/artifact.json` (immutable findings).
- `Repository` → `root/<2char>/<commit_id>/commit.json` with a parent/child DAG,
  sharded directories, `adopt_children_by_task` backfill.

Both are keyed off `task_id`↔`commit_id`, both write JSON per unit, both must be
cleared/loaded consistently. The git-like **sharding** (`<id[:2]>/<id>/`) buys
nothing at this scale and adds a lookup rule.

**Cost:** two mental models for "persist what an agent did"; duplicated clear/
load/link logic; the provenance DAG is the least-used output of the system.

### H4. A dual-UI render stack for one terminal
`cli/{terminal.py, tui.py}` + `present.py` (view-models) + `render.py` (engine
adapters) + `core/events_format.py` (one textifier). Two live, concurrently
maintained front-ends over the same engine.

**Cost:** every output change touches view-model + two adapters + formatter.
Elegant, but it is real overhead for an experimentation tool where the terminal
is the only user.

### H5. Prompt assembly is split across four places
`core/agent_system_prompt.txt` (static method/guidelines) + `Agent.run()` (task +
`[ROLE]` prepend) + `Agent._context_observation()` (environment + turn map +
task re-included every turn) + injected `EnvironmentInfo`. To change how an agent
sees its task, you edit several files.

**Cost:** hard to reason about the final prompt; easy to drift (we already fixed
one drift where env facts lived in two places).

### H6. Benchmarks mutate the process working directory
`benchmark/runner.py:run_one` calls `os.chdir(workspace)` / finally-restores the
global cwd. This works only because file tools fall back to `Path.cwd()` when no
`generated_root` is set, and the benchmark runtime factory sets **no**
`generated_root`. It's fragile, non-composable, and global.

### H7. A thicket of locks
`Runtime` owns `_path_locks`, `_lock_guard`, `_repo_lock`; `UsageTracker` a
per-agent lock; `Agent` a `_loop_lock` (`continue_with_input`). Several are for
edge cases exercised only in tests.

---

## 3. Simplification alternatives (with trade-offs)

### S1. Collapse to **one** run path: `runtime.run(description, ...) -> AgentOutcome`
Delete `AgentRunner`. Give `Runtime` a small `async run(description) -> Agent`
(or return `Agent`, caller reads `.outcome`). `Harness` becomes a thin config +
handler wrapper around `runtime.run`. Tests/CLI/benchmark all call the same thing.

- ✅ removes a class + duplicated outcome extraction; one mental path.
- ⚠️ Custom agents that `continue_with_input` (TUI `/new` reuses a root) still use
  `Agent.continue_with_input` directly — keep that public.
- *Effort:* small. *Risk:* low (all tests already use runtime+agent directly).

### S2. Drastically simplify `prune/restore`
Two options, pick one:

- **(a) Keep prune/restore but drop positional fidelity.** Restore always
  re-appends the turn at the *end* of the conversation (with a "restored" marker
  in line), not at the marker's exact slot. This deletes ~60 of the trickiest
  lines (marker-index fixing, downstream re-indexing) and the fragile tests.
  Trade-off: conversation order after restore is looser — acceptable for an LLM
  that asked to restore a specific turn.
- **(b) Drop in-flight prune and retention caps.** Keep only
  "prune(ids) → replace with a short marker; restore(pid) → append at end" and
  let the LLM fully own pruning. Removes `in_flight_prune`, `evict_overflow`
  complexity, and the `next_turn` dance.

Both cut `context.py` to roughly half and make it reviewable in one sitting.

### S3. Single, flat persistence layer
Replace sharded commit files + DAG with one store:

- Keep `ArtifactStore` as the only on-disk truth (already flat and stable).
- Replace `Repository` shards with a single append-only `commits.jsonl`
  (`task_id`, `agent_id`, `artifact_ids`, `parent_id`, `child_ids`, timestamp).
  Rebuild the tree in memory at load. Drop `<2char>/` sharding and the
  `adopt_children_by_task` backfill (one `commit` fn, no re-save of parents).

- ✅ one layering rule (`<store>/<obj_id>/` and `<store>/commits.jsonl`), one
  clear/load path, no row-re-encoding.
- ⚠️ Lose the pretty per-commit JSON files on disk (acceptable for scale < 1e5).
- Alternatively *fold commits into artifacts* (an artifact just carries
  `parent_id`), eliminating the second store entirely — simplest of all, at the
  cost of the "commit" abstraction the docs promise.

### S4. Decide the UI commitment and cut accordingly
- **If one terminal UI is enough** (recommended for an experiment): drop Textual
  `tui.py` and `render.py's` Textual adapter; keep Rich terminal only. Delete
  `cli/tui.py`, `tests/cli/test_tui_smoke.py`, and most of `render.py`.
  `present.py` (view-models) can stay as the single renderer input.
- **If both UIs are genuinely needed:** keep as is, but route *all* rendering
  through `present.py` + `format_event` and resist adding a third.

Being able to delete ~400 LOC of UI + its smoke test is the fastest real
"ease of development" win available.

### S5. Centralize prompt construction in one `PromptBuilder`
One module (e.g. `core/prompts.py`) composes, from inputs `{system_prompt.txt,
task, role, EnvironmentInfo, turn state}`:
- the initial `system` message,
- the `user` message (task + role),
- the per-turn observation block.

`Agent` calls only `PromptBuilder.build_*(...)`. Editing any prompt behavior =
one file. Keep `agent_system_prompt.txt` as the single static asset it imports.

### S6. Eliminate `os.chdir` in benchmarks — use the sandbox that already exists
Every file tool already resolves against `generated_root` (or cwd), and `bash`
runs with `cwd=generated_root`. So:

- Have the benchmark `runtime_factory` set `generated_root=<staged workspace>`.
- Delete `os.chdir(workspace)` / restore in `run_one` entirely; artifacts/repo
  stay relative to the true cwd as today.

Removes a global side effect, makes runs composable, and *strengthens the sandbox*
(the original intent of the staged workspace) instead of working around it.

### S7. One output-budget policy
Today content is truncated in three places: registry `token_limit*4`, `read`'s
400 KB cap, and the agent's `MAX_TOOL_RESULT_CHARS`. Make `ToolRegistry.execute`
the *only* place that sizes results (it already owns `token_limit/offset`), and
delete the two extra caps/constants. One rule, one knob.

### S8. Tune from config, not constants
Move the scattered magic numbers (`active_turn_window=50`, `max_pruned_retained=100`
in `agent.py:__init__`, `MAX_FETCH_BYTES`, `MAX_READ_CHARS`,
`MAX_TOOL_RESULT_CHARS`, bash default timeout) into `config.py`. New-dev-friendly:
everything tunable is discoverable in one schema.

---

## 4. A "target" simplified architecture

```
api/Harness ───────────────────────────────────────────┐
                                                        ▼
            Runtime.run(description) ──► Agent ──► RunLoop ──► ToolRegistry ──► ToolContext ──► tools
            │  ▲                                     │
            │  └── outcome                           └─ AgentContext (kept small: prune/restore append-only)
            ├─ ArtifactStore   (flat, single store)
            ├─ Repository      (commits.jsonl, in-memory tree)
            ├─ EventBus + format_event
            └─ UsageTracker
UI:  Rich terminal only ── present.py ── render.py (single adapter)
Prompt building: core/prompts.py (one place)
Benchmark: generated_root-based sandbox (no os.chdir)
```

Net effect if S1–S8 were taken: **`AgentRunner` deleted; `tui.py`+Textual adapter
deleted; `context.py` ~halved; `repository.py` ~halved and flattened; one render
adapter; one prompt builder; one result-budget rule; no global cwd mutation.** The
engine becomes ~40–45% less surface area with the same capabilities, and each new
dev has far less to learn.

---

## 5. Recommended order (cheap → valuable)

1. **S6** remove `os.chdir` — isolated, removes a global side effect (low risk).
2. **S1** delete `AgentRunner`, add `Runtime.run()` (touches CLI/API/tests).
3. **S7 + S8** one output-budget policy + central knobs.
4. **S5** `PromptBuilder` — consolidates the four prompt sources.
5. **S2** simplify prune/restore (drop positional restore) — biggest cognitive cut.
6. **S3** flatten persistence.
7. **S4** cut a UI (product decision — do last, it's the one with user-visible cost).

S1–S3, S5–S8 are internal and change no user-facing behavior; S4 is the only one
that removes a shipped feature.

---

## 6. What to keep (do not "simplify" this away)

- **Schema-driven tool dispatch + `ToolContext`** — this IS the product
  (structured tool calling). Keep it; it is already clean and testable.
- **Runtime/graph ownership + artifact handoff** — the core isolation idea.
- **`format_event` single textifier** even if one UI remains — keeps logs, TUI
  (if kept), and Harness logger consistent.
- **Deterministic benchmark verifiers/scoring** — genuinely better than
  LLM self-rating; only its *chdir mechanics* need fixing (S6).
- **`AgentOutcome` public surface** — made runner/metrics read public state; keep.

---

## 7. Execution status (implemented 2026-08-11, in recommended order)

All of S6 → S1 → S7/S8 → S5 → S2 → S3 → S4 applied. Test suite: **191 passing**,
run against `src` via the editable install. No user-facing behavior removed except
the Textual TUI (explicitly requested).

| Step | Done | What changed |
|------|------|--------------|
| S6 | ✅ | `benchmark/runner.py` no longer `os.chdir`s; `Runtime.set_generated_root(workspace)` makes the existing sandbox the working root. Global cwd side effect removed. |
| S1 | ✅ | Deleted `core/runner.py` (`AgentRunner`). Added `Runtime.run(description, *, role/system_prompt/agent_type/root_agent) -> Agent`. `Harness` and `cli/terminal.py` run through `Runtime.run`; `last_reports` derived from `root.outcome`. Rewrote `test_agent_loop.py` to target `Runtime.run`; updated `test_e2e.py` (removed redundant runner lines). |
| S7 | ✅ | Deleted the two extra result caps: agent `MAX_TOOL_RESULT_CHARS` and `read`'s `MAX_READ_CHARS`. `ToolRegistry.execute` is now the single output-budget rule. |
| S8 | ✅ | Centralized `active_turn_window` into `AgentConfig` (Runtime reads it); (the `max_pruned_retained` knob was added then removed in S2). |
| S5 | ✅ | New `core/prompts.py`: `AGENT_SYSTEM_PROMPT`, `build_user_message()`, `build_observation()`. `Agent` imports/uses these; prompt shaping lives in one file. |
| S2 | ✅ | `context.py` simplified ~40%: restore re-appends at end (no marker-index re-fixing), removed `in_flight_prune`, `evict_overflow`, retention caps, `in_flight_prune`. Agent/Runtime/config dropped `max_pruned_retained`. Updated prune/restore tests; deleted in-flight + cap tests. |
| S3 | ✅ | `Repository` flattened to a single append-only `commits.jsonl` (no `<id[:2]>/<id>/commit.json` sharding, no per-commit `_save(parent)` re-encoding; one `_flush`). Same public API; `test_repository.py` unchanged and passing. |
| S4 | ✅ | Deleted `cli/tui.py`, `tests/cli/test_tui_args.py`, `tests/cli/test_tui_smoke.py`; removed the Textual adapter from `cli/render.py` (kept Rich); removed `--tui` from `cli/terminal.py`; removed `textual` dep and the `dynamic-harness-tui` console script from `pyproject.toml`. |

Also: `scripts/run_optimize.py` migrated to `Runtime.run()` and `config.llm.verify_ssl`.
Docs synced (`AGENTS.md`, `README.md`, `docs/guides/getting-started.md`, `docs/api/tools.md`).

### Net result
- **Deleted files:** `core/runner.py`, `cli/tui.py`, `tests/cli/test_tui_args.py`, `tests/cli/test_tui_smoke.py`.
- **New files:** `core/prompts.py`.
- **Removed dependency:** `textual`.
- One run path (`Runtime.run`), one result-budget rule, one prompt builder, one
  flat provenance store, no global cwd mutation, single Rich terminal UI.

### Residual / optional follow-ups (not blocking)
- Could go further on S3 (fold commits into artifacts) if the "commit" abstraction
  becomes unnecessary.
- `agent.py` (~630 LOC) still holds the run loop; a `RunLoop` extraction remains an
  optional future step if it grows again.
