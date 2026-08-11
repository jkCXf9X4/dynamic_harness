# Architecture Review — Dynamic Harness

*Reviewer: read-only analysis agent. No source changes made. Covers `src/dynamic_harness/**`, `docs/VISION.md`, `docs/agent_methodology_guidelines.md`, and the test suite.*

**Overall verdict:** The separation of *Runtime (owns the task graph)* from *Agent (owns its own loop)* is a genuinely good idea, and the deferred-delegate mechanism that gives you real batch parallelism is the strongest piece of the design. However, the codebase is in a state where **boundaries are declared but not enforced**: the clean module seams are undermined by heavy private-attribute access across package borders, several "typed abstraction" layers (protocols, typed event dataclasses) exist but are unused, hierarchy is stored in four mutually-inconsistent places, and — the known gap — **there is no coordination primitive whatsoever for concurrent multi-agent writes to a shared repo**. Most findings below are of the "real problem, not style nitpick" kind.

---

## 1. Architectural soundness: is the Runtime/agent split clean?

The core idea is sound and mostly realized. An `Agent` does not know the task graph; the `Runtime` owns `_task_graph`, `_agents`, and the stores (`core/runtime.py:36-51`). Agents mutate only their private loop state and funnel all side effects through the Runtime. This is the right shape, and the sibling-isolation test (`test_agent.py::test_agent_has_no_sibling_visibility`) confirms the intent.

That said, the split leaks in several concrete ways:

### 1.1 Private-attribute access between Runtime ↔ Agent ↔ capabilities

- `agent.py:78` — `self._llm = runtime._llm`. The Agent reaches straight into the Runtime's private field to read the LLM. There is a public `set_llm()` for writing but **no getter** for reading, so every consumer is forced to poke the private field.
- `runtime.py:212` — `get_retries()` returns `agent._llm_retries`, reaching into an Agent's private field from the Runtime.
- `capabilities.py` is full of this. `_tool_delegate` reads `agent._deferred_delegates` and writes `agent._pending_child_task` (`capabilities.py:537-552`); `_tool_read_artifact` reads `agent._artifact_store` (`capabilities.py:570`); `_tool_prune`/`_tool_restore`/`_tool_compress` read and *rewrite* `agent._messages`, `agent._turns`, `agent._pruned`, `agent._prune_markers`, `agent._turn_counter` (`capabilities.py:700-891`). `_format_delegate_result` reads `child._runtime`, `child.parent`, `child._last_report`, `child._last_failure` (`capabilities.py:492-518`).

Some of this is defensible — prune/restore/compress are effectively "the agent's own hands" manipulating the agent's own message list. But it makes `capabilities.py` the owner of a substantial chunk of the Agent's core state machine (`_messages` assembly for pruning is ~150 lines living in the tool file), and it makes the file coupling a hard dependency on private field *names*. Rename `_messages` and half the tool layer silently breaks.

### 1.2 Latent circular import (worked around, not solved)

`agent.py` imports from `capabilities.py` *inside function bodies* to avoid a cycle:

- `agent.py:191` — `from ..core.capabilities import _make_prune_marker`
- `agent.py:492` — `from ..core.capabilities import _format_delegate_result`

`capabilities.py` imports `Agent` only under `TYPE_CHECKING` (`capabilities.py:16-17`). The cycle is real: the **Agent** needs helpers that produce **prune markers / delegate results**, and the **tools** need the **Agent** type. The deferred imports dodge the runtime cycle but signal that the responsibility boundary is drawn in the wrong place — factory helpers that take an `Agent` arguably belong on the Agent itself or in a neutral module, not behind a `TYPE_CHECKING` workaround.

### 1.3 Coupling to the "terminal tool" convention

The agent loop hard-codes a dominance check `if has_delegates` (`agent.py:380`) and special-cases `delegate` by injecting a hidden `_tool_call_id` kwarg (`agent.py:393-394`). The tool registry's `openai_schemas()` also injects `token_limit`/`token_offset` into *every* tool's schema (`capabilities.py:86-93`). Both are pragmatic but represent implicit contract coupling: the loop knows too much about the `delegate` tool specifically. If a future tool needs deferred behavior, it can't get it without modifying the loop.

---

## 2. Module boundaries

### 2.1 `core/` is a god-package

`core/` holds *everything that matters*: models (`task.py`), the runtime, the agent, all 17 tools (`capabilities.py`, 932 lines), the event bus, the trace store, usage tracking, protocols, and the runner. Two of the three largest files in the project (`capabilities.py` 932, `agent.py` 562) are the two most tightly coupled to each other. The `artifact/`, `memory/`, and `llm/` packages are clean and small; the weight of the system lives in `core/`, which is where the coupling is concentrated. This isn't fatal, but it means the only "boundary" that matters day-to-day is the one between `agent` and `capabilities`, and that one is leaky.

### 2.2 Dead abstraction layers — boundaries declared but not enforced

- `core/protocols.py` defines `LLMProviderProto`, `ArtifactStoreProto`, `RepositoryProto`, `EventBusProto`, `UsageTrackerProto`. **Nothing uses them.** The code talks to concrete classes (and private attributes) directly. These Protocols are aspirational documentation, not enforced seams, and they're now drifting from reality (e.g. `Runtime.get_retries` isn't in any protocol).
- `core/events.py` defines typed dataclasses `IterationData`, `LLMCallEndData`, `ToolCallStartData`, `ToolCallEndData`, `DelegationStartData`, `DelegationEndData`, `CompressionData`, `SafetyWarningData` — but every single emission site passes a raw `dict` as `ActivityEvent.data` (`agent.py:256-263, 316-324, 341-350, ...`). The typed payloads are 100% dead code. Either emit the typed payloads or delete the dataclasses; right now a reader assumes structure that the code never produces.
- `capabilities.py:423` `_build_gitignore_filter()` is dead — `Runtime.get_gitignore_filter()` (with mtime caching, `runtime.py:57-76`) is the live implementation, and it *duplicates* the same gitignore logic a second time.
- `task.py:30` `DelegateRequest` is defined and exported but never constructed anywhere.

### 2.3 Duplicated event rendering across three places

The exact "format an `ActivityEvent` as a string" switch exists three times: `cli/terminal.py:_format_event()` (`terminal.py:53-84`), handlers inside `cli/tui.py`, and `api/harness.py:_on_activity()` (`harness.py:103-136`). Three separate event→text mappings that will drift. Rendering is presentation-layer and belongs in the CLI, but it should live in exactly one helper.

### 2.4 `harness.py` hard-codes the LLM

`api/harness.py:_configure_llm` (`harness.py:77-86`) and `cli/common.py:build_runtime` (`common.py:65-72`) both construct `OpenAIProvider` directly. A programmatic user of `Harness`/`Runtime` cannot inject a custom `LLMProvider` through the public API at all — only through `runtime.set_llm()`, which bypasses the wrapper. The provider ABC is clean (`llm/provider.py`), but it isn't reachable via the highest-level facade.

### 2.5 `benchmark/` is undocumented

`benchmark/` is a real, sizable package (scoring, metrics, tasks, runner) that appears nowhere in `AGENTS.md`'s directory map. It's fine that it exists, but the project's own onboarding doc is stale relative to the tree.

---

## 3. Data models (`core/task.py` and friends)

### 3.1 Hierarchy is stored four ways (inconsistent sources of truth)

The parent↔child relationship is represented as:
1. `Task.parent_id: str | None` (`task.py:24`)
2. `Runtime._task_graph: dict[str, list[str]]` (`runtime.py:37`)
3. `Agent.parent` (object reference) + `Agent.children` (`agent.py:48-49`)
4. `Commit.parent_ids` / `Commit.child_ids` (`repository.py:18-19`)

These are not kept coherent. Most importantly, **(4) is wired incorrectly — the commit graph is disconnected in the real runtime flow.**

`Runtime.deliver_report` creates the commit with `parent_ids=[agent.task.parent_id]` (`runtime.py:141`) — that is the parent's **task id**. But `Repository.commit` links by **commit id** (`repository.py:49`: `self._commits.get(pid)`), and there is no `task_id → commit_id` mapping anywhere. When a child reports, the parent's commit either doesn't exist yet or is keyed by a UUID unrelated to the task id, so `Repository.commit` finds nothing to link and `parent.child_ids` never gets populated. The unit tests in `test_repository.py:22-27` pass *commit* ids and pass — hiding that the *runtime* feeds it *task* ids. The `repository.tree()` view will show every node as orphaned. This is a genuine bug, and a direct consequence of the four-way duplication: nothing enforces that the ids put into `Commit.parent_ids` are commit ids.

### 3.2 `ReportPayload.artifact_ids` is overloaded (paths vs. UUIDs)

The field is documented as *"Paths/files written to disk"* (see `AGENTS.md`, and the `report` tool description `capabilities.py:193-223`, and the VISION doc's "reference files by path"). But `deliver_report` does:

```python
artifact_ids=payload.artifact_ids + [artifact.id],   # runtime.py:140
```

so the list mixes arbitrary filesystem paths supplied by the LLM with the freshly generated artifact UUID. Then `test_runtime.py::test_artifact_store_populated_on_report` asserts that **every** entry in `commit.artifact_ids` resolves via `artifact_store.get(aid)` (`test_runtime.py:56-59`) — which can only be true for real UUIDs. So: the tool/contract tells the agent to pass paths, the commit stores those paths, and anyone reading them back through the store gets `None`. The two meanings should be split (e.g. `files_written: list[str]` vs `artifact_ids: list[str]`).

### 3.3 Nullable/under-constrained fields

- `ReportPayload.confidence: float | None` has no bounds — a model can report `confidence=5.0`. A `Field(ge=0, le=1)` would be free.
- The `ReportPayload` outcome is inferred from the channel (report/succeed) rather than modeled — but `Task.status` already models `failed`/`escalated`/`completed`. There's no cross-check that an agent that called `fail()` can't also have a report. The redundancy is fine, but `ReportPayload` carries `technical_summary`/`full_report`/`confidence` as unconstrained optionals when the "progressive disclosure" concept (`ArtifactView`) already has 6 named view fields — the two models duplicate the same layered-summary idea in different shapes.
- `Task.role` and `Task.system_prompt` both override agent behavior with implicit precedence/concatenation inside `run()` (`agent.py:109-115`) — role text is glued onto the user message and system_prompt replaces the default prompt. This precedence is undocumented magic; a small doc/comment or a single `build_user_message()` helper would help.

### 3.4 Type convention drift

- `ToolResult` (`capabilities.py:37-40`) is a hand-rolled class despite the stated convention "Pydantic models for all data structures."
- Duplicate tool-call structs: `ToolCallData` (llm/provider.py) and `ToolCall` (core/capabilities.py) represent the same `(id, name, arguments)` triple and are manually converted in `agent.py:359-372`. One canonical type would remove the mapping.
- `Task.metadata: dict[str, Any]` and `ActivityEvent.data: dict[str, Any]` are untyped by design, but given the unused typed-event dataclasses, the code pays for structure it doesn't use.

Overall the models are *coherent enough* and the nullable fields are defensible; the real issues are the overloaded `artifact_ids`, the broken commit-parent linkage, and the four-way hierarchy duplication, not field count.

---

## 4. Concurrency

### 4.1 How the deferred-delegate resync works (and it's basically right)

The mechanism in `agent.py:380-435` + `capabilities.py:_tool_delegate` is the best part of the runtime and correctly gives batch parallelism:

1. When a single LLM response contains ≥1 `delegate` tool call, the loop sets `self._deferred_delegates = []` (`agent.py:380-382`).
2. Each `delegate` execution (via `_tool_delegate`) checks `if agent._deferred_delegates is not None` (`capabilities.py:537`) — because it is a list, it appends `(_tool_call_id, child, asyncio.create_task(child.run()))` and returns `"pending"` **without awaiting**. So all delegates in the batch are launched as background tasks and the parent does not block per-call.
3. After the batch's tool calls finish, `_gather_deferred_and_finalize` (`agent.py:485-508`) awaits the child tasks and splices each child's formatted result back into the matching `results[tool_call_id]` via `deferred_map`. The terminal-tool early-return path (`agent.py:422-430`) handles the case where a batch contains both a `delegate` and a terminal tool in the same response.

This gives you real concurrent children *within* a single parent turn, matching the "delegate in parallel in ONE turn" doctrine (`agent_methodology_guidelines.md` P1). Credit where due: the resync is correct and the in-memory state changes in the loop are atomic because nothing in the batch loop awaits between `_messages`/`_turns` mutations.

Three problems in this mechanism:

- **(a) Child exceptions crash the parent.** `_gather_deferred_and_finalize` catches only `asyncio.CancelledError` when awaiting children (`agent.py:500-502`). A *non-cancellation* exception raised inside `child.run()` will propagate and escape the parent's `_run_loop` — and `Agent.run` only guards `CancelledError` (`agent.py:120-131`). Deferred children are *detached* background tasks, so one misbehaving custom child takes down the whole parent. Contrast with `fail()`-based failures, which are contained; exception-based failures are not. Recommended: `await asyncio.gather(*tasks, return_exceptions=True)` and convert any exception into a `self.fail(...)`.
- **(b) Dead path.** The non-deferred `_pending_child_task` await branch in `_tool_delegate` (`capabilities.py:541-552`) is effectively unreachable: `_deferred_delegates` is set to a non-None list whenever any `delegate` executes, so `_tool_delegate` always takes the append-and-return-pending branch. The synchronous-await path is legacy and now just confuses readers.
- **(c) Serial await of parallel children.** `_gather_deferred_and_finalize` awaits children one-by-one in a `for` loop (`agent.py:498-503`) rather than `asyncio.gather`. Because the child tasks already run concurrently in the background, serial `await`s pick them up as they complete, so *wall-clock* concurrency is preserved — but `gather(return_exceptions=True)` would be clearer and uniformly error-handled.

### 4.2 The known gap: no coordination primitive for same-repo multi-agent work

This is real and unaddressed. Every agent shares the same `runtime.generated_root`, the same `Path.cwd()`, and the same repository dirs. The **`write`, `edit`, and `bash` tools operate on that shared filesystem with zero locking** (`capabilities.py:398-412, 479-489, 631-659`). Two parallel leaf agents (the intended multi-agent use case) can:

- call `write(path, ...)` on the same path and clobber each other (lost update; the "no change" guard at `capabilities.py:406-411` even reads before publishing, so interleaving read→write→read→write is entirely possible),
- run conflicting `bash` `git ...` mutations against the same repo concurrently.

There is **no** per-path mutex, no exclusive file-create, no per-agent worktree, no version/branch isolation. The in-memory structures (`_agents`, `_task_graph`, `_artifacts`, `_commits`) are mostly safe because their mutations are synchronous with no `await` inside them (cooperative scheduling prevents torn updates within a single method — e.g. `Repository.commit` is non-awaiting, so sibling `child_ids` appends don't interleave). The hazard is specifically the **shared filesystem**, and it's the thing the whole architecture is meant to exploit (agents writing artifacts and editing a shared repo).

**Simplest acceptable remedy (recommended):** a per-path keyed lock owned by the Runtime.

```python
# runtime.py
self._path_locks: dict[Path, asyncio.Lock] = {}

async def workspace_lock(self, path: Path) -> asyncio.Lock | None:
    if path is None:
        return None
    return self._path_locks.setdefault(str(path), asyncio.Lock())
```

Then `write`/`edit` acquire `async with await agent.get_workspace_lock(safe):` around the read-modify-write. Additionally, serialize `bash` commands that mutate a repo through a *single* global repo lock (or route git mutations to a dedicated locked tool). This is ~20 lines, understandable, and directly closes the known gap. A heavier but more "correct" alternative — per-agent private worktree + parent-side merge — is a much larger change and is *not* worth it for now.

### 4.3 `converse` / `continue_with_input` re-entrancy

`_tool_converse` (`capabilities.py:894-912`) calls `target.continue_with_input(message)`, which re-enters a (usually completed) agent's `_run_loop` and mutates the same `_messages`/`_turns` between `await`s (`agent.py:133-140`). Nothing prevents two parents from `converse`-ing the *same* target agent concurrently, which would interleave two run-loops on one message list. A per-agent `asyncio.Lock` serializing `_run_loop`/`continue_with_input` is the cheap fix; given the current single-caller usage it's low priority, but it's the same missing primitive as 4.2.

### 4.4 `Runtime.reset()` while tasks run

`Runtime.reset()` (`runtime.py:220-231`) clears stores and repo while `_agents`/background tasks may still hold references; in interactive mode `/reset` during an in-flight run could leave background children writing to a cleared store/root. Minor, but worth guarding (cancel pending tasks on reset).

---

## 5. Evaluation of alternatives

For the biggest decisions, are there simpler options worth taking?

**5.1 Sequential delegation instead of deferred-delegate parallelism.**
The synchronous `_pending_child_task` path already exists and is far simpler (await each child inline). *Verdict: **not worth switching to.*** It directly contradicts the "delegate in parallel in one turn" doctrine that is the architecture's raison d'être; batch parallelism is the whole point. Keep the deferred mechanism. The cheap improvement is swapping the manual task list for `asyncio.gather(return_exceptions=True)` (5a, clearer + child-error containment) — small, worth doing.

**5.2 Make the Runtime the coordination owner.**
Alternative: have agents coordinate via a central Runtime-owned lock/lease registry (as in 4.2) vs. giving each agent an isolated worktree. *Verdict: central path-keyed locks are the right minimal step and worth taking; worktree isolation is not worth it now* (large change, merging complexity, and the artifact/commit stores would need re-plumbing). A lease/lock with no TTL is the simplest thing that makes the current shared-file model safe.

**5.3 Remove the parallel hierarchy storage (drop `_task_graph` and/or commit parent/child).**
Since `Task.parent_id` already records parentage, `Runtime._task_graph` and `Commit.parent_ids/child_ids` are redundant projections. *Verdict: worth simplifying.* Keep `task_graph()` as a *derived* view (build from `Task.parent_id` on demand) rather than a maintained dict — this removes one of the four inconsistent sources of truth and the broken commit-linkage bug evaporates with it. This is a moderate refactor; a lower-effort intermediate is to fix the wiring so `Commit.parent_ids` carries commit ids (or task ids are mapped to commit ids), which un-breaks the provenance graph.

**5.4 Two provider-facing tool-call structs (`ToolCallData` vs `ToolCall`).**
Alternative: a single struct everywhere. *Verdict: trivially worth it* — it's a mechanical dedup that removes a manual conversion and one type. Low risk, low reward but cheap.

**5.5 Enforce module seams via a small interface instead of private attributes.**
Alternative: narrow getters (`runtime.provider`, `runtime.acquire_path_lock`, etc.) and move prune-marker/delegate-result helpers onto `Agent`. *Verdict: worth doing as cleanup, not as a big Protocol-driven rewrite.* The `Protocol`s in `core/protocols.py` should either be wired in to type-check or deleted; a lightweight getter-based boundary is more understandable than a sprawling protocol layer for an internal project.

---

## 6. Improvement priorities (ranked)

1. **Add the same-repo coordination primitive (High — closes the declared known gap).** Path-keyed `asyncio.Lock` on the Runtime for `write`/`edit`, plus a single repo-wide lock for git-mutating `bash`. This is the one thing that directly threatens the architecture's core promise (parallel agents producing/merging artifacts on a shared repo) and it's cheap and understandable. *`runtime.py`, `capabilities.py` write/edit/bash.*

2. **Contain child-task exceptions so they can't crash the parent (High).** Replace the manual loop in `_gather_deferred_and_finalize` with `asyncio.gather(..., return_exceptions=True)` and route non-cancellation failures to `self.fail(...)`. Also delete the dead `_pending_child_task` await branch. *`agent.py:485-508`, `capabilities.py:541-552`.*

3. **Fix the broken commit parent/child lineage (High — data-integrity).** `deliver_report` passes a task id into `Commit.parent_ids` where the repository expects a commit id, so `repository.tree()` is disconnected in real runs (and the unit tests hide it by passing commit ids). Map task ids to commit ids (keep a `task→commit` index in the Repository) or feed real commit ids. *`runtime.py:136-143`, `repository.py:40-56`.*

4. **Disambiguate `ReportPayload.artifact_ids` (Medium).** Split "files written to disk" (paths) from "stored artifact ids" (UUIDs) so `commit.artifact_ids` is uniformly resolvable via `artifact_store.get()`, matching `test_runtime`'s own invariant. *`task.py:43`, `runtime.py:140`.*

5. **Cut dead/duplicate abstraction (Medium).** Remove `DelegateRequest`, `_build_gitignore_filter`, the unused typed event dataclasses in `events.py`, and either wire up or drop `core/protocols.py`. Consolidate the three copies of event→text rendering into one helper. *`task.py`, `capabilities.py`, `events.py`, `protocols.py`, `cli/terminal.py`, `cli/tui.py`, `api/harness.py`.*

6. **Replace private-attribute access with narrow getters (Medium).** Add `runtime.provider`/`set_provider` and `agent.resolve_workspace_lock`, move `_make_prune_marker`/`_format_delegate_result` onto `Agent`, and stop `Runtime.get_retries` poking `agent._llm_retries`. This removes the latent `agent↔capabilities` cycle and the fragile field-name coupling. *`agent.py`, `capabilities.py`, `runtime.py`.*

7. **Serialize `converse`/`continue_with_input` re-entrancy (Low-Medium).** A per-agent lock around the run loop prevents interleaved loops if two parents converse the same child. *`agent.py`, `capabilities.py:_tool_converse`.*

8. **Harden `Runtime.reset()` during active runs (Low).** Cancel/await in-flight agent tasks before clearing stores. *`runtime.py:220`.*

---

## What's genuinely good (call it out)

- **The deferred-delegate mechanism** (`agent.py:380-435`, `capabilities.py:_tool_delegate`) is a legitimate, working piece of async concurrency design — it delivers the batch-parallel delegation the methodology demands.
- **The `llm/` package** is clean: a small ABC (`provider.py`) with a single concrete `OpenAIProvider`, and `aclose()` is properly threaded through `Runtime.aclose()`.
- **Safety invariants** (max-iterations, repeated-call detection, prune/compress/restore) are real, tested, and live mostly inside the agent loop where they belong.
- **Tests are meaningful**: the deterministic `_ToolLLM` mock gives byte-level reproducibility for loop behavior, and the sibling-isolation and prune/restore tests exercise genuinely tricky behavior.
- **The safe-path sandbox** (`capabilities.py:_resolve_safe_path`) and IP restriction in `webfetch` (`capabilities.py:466-471`) show real security awareness.

The architecture has a strong skeleton and one excellent concurrency pattern; the work that remains is *enforcement of its own boundaries* and *one missing coordination primitive*.
