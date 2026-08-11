# Implementation Plan — Addressing the Architecture Review

*Companion to `review.md` in this folder. Maps each finding to concrete, verifiable changes. This plan makes **no change itself**; it is the spec for follow-up work.*

## Reading guide

- **ID** ties each item to the review.
- **Files** — module(s) touched.
- **Change** — what to do, at symbol granularity.
- **Acceptance** — how to prove it worked (tests / commands).
- **Effort** — S (small, <1 session), M (1–2), L (2+).
- Priority column: P0 (data integrity / safety / concurrency), P1 (cleanup & clarity), P2 (nice-to-have).

---

## P0 — Data integrity, concurrency, robustness

### P0-1. Add a same-repo coordination primitive (closes the declared known gap)

**Finding:** review §4.2. `write`/`edit`/`bash` operate on a shared `generated_root` with no locking.

**Files:** `core/runtime.py`, `core/agent.py`, `core/capabilities.py`.

**Change:**
1. `Runtime` gains a lock registry and an accessor:
   ```python
   # runtime.py
   self._path_locks: dict[str, asyncio.Lock] = {}
   self._repo_lock = asyncio.Lock()
   self._lock_guard: asyncio.Lock = asyncio.Lock()  # guards dict mutation

   async def acquire_path_lock(self, path: str) -> asyncio.Lock:
       async with self._lock_guard:             # serialize dict setdefault
           lock = self._path_locks.setdefault(path, asyncio.Lock())
       return lock
   ```
2. `Agent` exposes `async def workspace_lock(self, path)` delegating to `runtime.acquire_path_lock`. Replace direct `runtime.generated_root` reads in tools where relevant.
3. **`_tool_write`** (`capabilities.py:398`) and **`_tool_edit`** (`capabilities.py:479`): wrap the read→compute→write in `async with await agent.workspace_lock(safe_path_str):`. Make `_resolve_safe_path` resolver reusable before acquire (resolve first, then lock the resolved string).
4. **`_tool_bash`** (`capabilities.py:631`): acquire a single `runtime._repo_lock` around subprocess execution when the command is a known repo-mutating verb (`git`, `rm`, `mv`, `find -delete`, `touch`, ...). Conservative default: hold the global repo lock for **all** bash when `generated_root` is shared. Document the tradeoff (serializes independent reads — acceptable; reads are usually cheap).
   - Expose this via `Agent.repo_lock() -> asyncio.Lock`.
5. `Runtime.reset()` clears `_path_locks` (add to existing body).

**Acceptance:**
- New test: two tasks concurrently `write` to the *same* path via real agents (or direct `_tool_write` with an injected delay) must not interleave → assert final file equals one of the two full contents, never a torn mix.
- New test: `concurrent_edits` — parallel `edit` calls on one file produce a deterministic, non-corrupted result.
- Existing `test_tool_interaction.py` token-limit read tests still pass (read is unchanged).

**Effort:** M. **Risk:** low; additive.

---

### P0-2. Contain child-task exceptions so they cannot crash the parent

**Finding:** review §4.1(a), §5.1.

**Files:** `core/agent.py`, `core/capabilities.py`.

**Change:**
1. Replace the loop in `_gather_deferred_and_finalize` (`agent.py:497-503`):
   ```python
   tasks = [t for _, _, t in pending]
   results_ = await asyncio.gather(*tasks, return_exceptions=True)
   # map error -> record failure + empty result instead of raising
   ```
   For each task that returned an `Exception`, set a placeholder tool result like `"Error: child agent raised: <exc>"` and record a failure on the child if not already failed (`child.fail(str(exc))` guarded by `hasattr`/try).
2. Remove the now-dead `_pending_child_task` await branch in `_tool_delegate` (`capabilities.py:541-552`) and the `_pending_child_task` attribute (`agent.py:64`), plus its cancellation handling in `run()` (`agent.py:123-128`). Confirm nothing else references it (grep first).
3. Optionally wrap `run()`'s `_run_loop()` call (`agent.py:121`) so any unexpected exception is converted to `self.fail(...)` rather than propagating (defense-in-depth for the root).

**Acceptance:**
- New test: a `FailingAgent` whose `run()` **raises** (not `fail()`) is delegated by a parent using the real loop; assert parent completes (status `completed` or `failed` with a coherent failure), never a leaked `Exception`/`CancelledError`.
- Existing `test_agent_loop.py::test_runner_cancel_via_task_cancellation` still passes (CancelledError still propagates as intended at the top level).

**Effort:** S–M.

---

### P0-3. Fix the broken commit parent/child lineage

**Finding:** review §3.1. `deliver_report` passes a *task* id into `Commit.parent_ids` which the repository treats as *commit* ids → disconnected `repository.tree()`.

**Files:** `core/runtime.py`, `memory/repository.py` (+ `memory/__init__.py` exports as needed).

**Change (preferred option A — repository owns the mapping):**
1. `Repository` maintains `_task_commits: dict[str, str]` mapping `task_id → latest commit id` (loaded during `_load_existing` by scanning each commit's `task_id`; updated in `commit()`).
2. Add `Repository.commit_for_task(task_id) -> Commit | None` and `Repository.get_parent_commits(task_id) -> list[Commit]` (task's lineage via each task's parent... note: multiple parents are possible per task if re-runs — use latest).
3. In `Runtime.deliver_report` (`runtime.py:136-143`), replace `parent_ids=[agent.task.parent_id]` with:
   ```python
   parent_ids = self.repository.commit_ids_for_tasks([agent.task.parent_id])
   # [] when no parent commit exists yet
   ```
4. `Repository.commit()` already links `child_ids` when a parent is found (`repository.py:49-55`); with real commit ids this now fires.

**Acceptance:**
- Update `test_runtime.py` or add `test_repository.py` case: run a parent that delegates two children which report; assert `repository.tree(root_commit_id)` lists both child commit ids, recovering from the artifact-store the child ids.
- Existing `test_repository.py` parent/child tests (which pass commit ids directly) remain green and now match the runtime path.

**Effort:** M.

---

## P1 — Clarity, contract, cleanup

### P1-4. Disambiguate `ReportPayload.artifact_ids`

**Finding:** review §3.2.

**Files:** `core/task.py`, `core/runtime.py`, `core/capabilities.py` (report tool def + `_tool_report`), `AGENTS.md`, docs describing the `report` tool.

**Change:**
1. Add a distinct field: `files_written: list[str] = Field(default_factory=list)` (“paths the agent wrote to disk”) to `ReportPayload` (`task.py:43`).
2. Keep `artifact_ids` meaning only *stored artifact UUIDs* (populated by the system, not the LLM).
3. `_tool_report`/`TOOL_REPORT_DEF` (`capabilities.py:193-223, 557`) accept `files_written`; stop advertising `artifact_ids` as “paths”.
4. `deliver_report` (`runtime.py:136-143`): store `files_written` where appropriate (e.g. written into the artifact view or a sidecar), and set `commit.artifact_ids=[artifact.id]` only.
5. Update `docs/agent_methodology_guidelines.md` (report-format section) and `AGENTS.md` ReportPayload block to reflect the split.

**Acceptance:**
- Reading `commit.artifact_ids` always yields entries where `artifact_store.get(id)` is non-None — which `test_runtime.py::test_artifact_store_populated_on_report` already enforces; it becomes always-green even with paths supplied.
- New test: agent reports with `files_written=[...]`; assert the files are referenced correctly and not in `commit.artifact_ids`.

**Effort:** S–M.

---

### P1-5. Cut dead / duplicated abstraction

**Finding:** review §2.2, §2.3; §3.4.

**Files:** `core/task.py`, `core/capabilities.py`, `core/events.py`, `core/protocols.py`, `core/__init__.py` (exports), `cli/terminal.py`, `cli/tui.py`, `api/harness.py`.

**Change:**
1. Delete `DelegateRequest` (`task.py:30`) and its export in `core/__init__.py:22`; grep for references first.
2. Delete `capabilities._build_gitignore_filter` (`capabilities.py:423`) — superseded by `Runtime.get_gitignore_filter`. Grep for other callers first.
3. Either (a) delete the typed event dataclasses in `events.py:10-65` and rely on `ActivityEvent.data` dicts, **or** (b) make emissions construct them. Recommend (a) delete to match reality; if event structure is needed, add a single `EventPayload` union later.
4. `core/protocols.py`: either wire the Protocols into type hints (large) or delete the file. Recommend **delete** and add narrow getters instead (see P1-6) — less ceremony for an internal project.
5. Consolidate the three event→text renderers (`terminal.py:53`, `tui.py`, `harness.py:103`) into one helper, e.g. `cli/format_event.py: def format_event(event)` used by both CLIs; `api/harness.py` keeps only its logger-specific formatting.

**Acceptance:**
- `grep -rn 'DelegateRequest\|_build_gitignore_filter\|IterationData\|LLMCallEndData' src` returns nothing (except possibly docs).
- `pytest tests` green (imports that referenced deleted symbols would fail loudly — catch them).

**Effort:** M. **Risk:** low, but do deletions in small commits and grep before each.

---

### P1-6. Replace private-attribute access with narrow getters (remove latent cycle)

**Finding:** review §1.1, §1.2.

**Files:** `core/runtime.py`, `core/agent.py`, `core/capabilities.py`.

**Change:**
1. `Runtime`: add `@property def provider` (returns `_llm`) and keep `set_llm`. Update `agent.py:78` to `self._llm = runtime.provider`.
2. `Runtime.get_retries` (`runtime.py:212`): return from a tracked counter (e.g. `self._agent_retries: dict[str,int]` incremented in the retry loop) instead of reading `agent._llm_retries`. Symmetric: `total_retries` (`runtime.py:215`).
3. Move `_make_prune_marker` and `_format_delegate_result` **onto** `Agent` as methods (e.g. `Agent.make_prune_marker(pid)`, `Agent.format_delegate_result(child)`), so `capabilities.py` calls public methods instead of reaching into `child._runtime`/`_last_report`. `_tool_prune`/`_tool_restore`/`_tool_compress` then use Agent methods for the marker bookkeeping (or accept a `hlp` param).
4. Remove the deferred imports `agent.py:191,492` once helpers live on Agent; `capabilities.py` uses `Agent` under `TYPE_CHECKING` only as before — **no runtime cycle returns** because agent no longer imports capabilities at call site.

**Acceptance:**
- `grep -rn 'runtime\._llm\|\._llm_retries' src` → none.
- `python -c "import dynamic_harness"` succeeds (no cycle).
- Full `pytest tests` green.

**Effort:** M. This is the highest-churn P1; do it after P0.

---

### P1-7. Serialize `converse` / `continue_with_input` re-entrancy

**Finding:** review §4.3.

**Files:** `core/agent.py`, `core/capabilities.py` (`_tool_converse`).

**Change:**
1. `Agent.__init__` adds `self._loop_lock = asyncio.Lock()`.
2. Wrap `continue_with_input` body (`agent.py:133-140`) in `async with self._loop_lock:` so two parents can’t interleave two runs on the same target. Same for the tail of `run()` if re-entered.
3. `_tool_converse` (`capabilities.py:894`): leave as is — the lock in the target handles serialization.

**Acceptance:**
- New test: two coroutines call `converse` on the same target concurrently; assert target’s message list ends in a deterministic order with no torn state.
- Existing converse test in `test_capabilities.py` passes.

**Effort:** S.

---

## P2 — Nice-to-have

### P2-8. Harden `Runtime.reset()` during active runs

**Finding:** review §4.4.

**Files:** `core/runtime.py`.

**Change:** In `reset()` (`runtime.py:220`), before clearing stores, cancel/await any in-flight agent tasks. Track agent run tasks (e.g. `self._agent_tasks: set[asyncio.Task]`) populated when `_tool_delegate`/`runner` creates them; on reset, `for t: t.cancel(); await` swallow `CancelledError`.

**Acceptance:** New test: start a slow agent, call `reset()`, assert no warning/exception and clean store state.

**Effort:** S.

---

### P2-9. Dedupe provider-facing tool-call structs

**Finding:** review §3.4.

**Files:** `llm/provider.py`, `core/capabilities.py`, `core/agent.py`.

**Change:** Make `ToolCall` (`capabilities.py:31`) the single canonical struct; have `openai_provider.py` return `ToolCall` (or convert in one place) and remove the manual `ToolCallData → ToolCall` block in `agent.py:359-372`.

**Acceptance:** grep for `ToolCallData` → only provider internal; `pytest tests` green.

**Effort:** S–M.

---

### P2-10. Expose custom LLM via the high-level facade

**Finding:** review §2.4.

**Files:** `api/harness.py`.

**Change:** Add `Harness(..., llm: LLMProvider | None = None)`; if provided, `runtime.set_llm(llm)` instead of hard-coding `OpenAIProvider` (`harness.py:77`).

**Acceptance:** New test in `test_e2e.py` or `test_harness`: construct `Harness(..., llm=MockLLM)` and assert it’s used.

**Effort:** S.

---

## Sequencing & dependencies

```
Phase 1 (correctness, do first — each is independently shippable):
  P0-2  child-exception containment   (needs grep for _pending_child_task)
  P0-3  commit lineage                 (touches Repository; independent)
  P0-1  workspace locks                (additive; independent)

Phase 2 (cleanup — best done after the above so names are stable):
  P1-4  artifact_ids split
  P1-6  getters / remove cycle   ← prerequisite for removing deferred imports
  P1-5  dead-code removal            (do P1-6 first to avoid touching removed names)
  P1-7  converse lock               (trivial, anytime)

Phase 3 (nice-to-have):
  P2-8, P2-9, P2-10

Suggested order: P0-3 → P0-2 → P0-1 → P1-4 → P1-6 → P1-5 → P1-7 → P2-*
```

**Recommended first task:** P0-3 (commit lineage) — it is the only one that is an outright data bug, small, and independently verifiable.

## Global acceptance gate

After each phase, run from repo root:
- `pytest` — full suite green
- `python -c "import dynamic_harness"` — no import cycle
- `grep -rn '<deleted symbol>' src` → no hits
