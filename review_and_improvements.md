# Dynamic Harness: Code Review and Improvement Suggestions

## Overview

This is a well-architected recursive agent harness designed around **artifact-based communication**, **strict encapsulation** (actor model), **Git-like provenance**, and **disposable workers**. The code is clean, well-structured, and faithful to the design vision laid out in `starting_point.md`. Below is a thorough review organized by severity.

---

## 🚨 Critical Issues

### 1. `Agent.run()` does not stop execution after `report()` / `fail()` / `escalate()`

**Location:** `src/dynamic_harness/core/agent.py`, lines 68-96

When the LLM calls `report()`, `fail()`, or `escalate()`, the agent's status is updated in the Runtime, but the tool loop in `run()` only checks `self.task.status == TaskStatus.completed` **after processing all tool calls in the current turn**. However:

- The `report` tool handler calls `agent.report()` which calls `runtime.deliver_report()` which sets `task.status = TaskStatus.completed`. But the `_tool_report` function always **returns a success string**, making the LLM think it can continue.
- If the LLM calls `report()` together with other tools in the same turn, those other tools run first (since results are collected into the message list regardless), and then the loop checks status.
- If the LLM calls `report()` as the only tool call, the loop checks status and returns. But if the LLM decides to make **another tool call** in a subsequent turn (because the tool result didn't signal termination), it will keep going.

**The real problem:** The tool loop only checks `self.task.status` after processing batch tool calls, but doesn't check after each individual tool call. If `report`, `fail`, or `escalate` are called, the agent should stop processing **immediately**, not after the current batch.

Also, `fail()` and `escalate()` set different statuses (`failed`, `escalated`) but the loop only checks for `completed`:

```python
if self.task.status == TaskStatus.completed:
    return
```

This means failing or escalating doesn't stop the loop either.

**Fix suggestion:**

```python
# In agent.py run() method, check after EACH tool call:
for tc in response.tool_calls:
    # ... build assistant_msg ...
    result = await self._runtime.tool_registry.execute(...)
    results.append(...)
    
    # NEW: check if we should stop after each tool call
    if self.task.status in (TaskStatus.completed, TaskStatus.failed, TaskStatus.escalated):
        messages.append(assistant_msg)
        messages.extend(results)
        return  # Or break out
```

---

### 2. `_on_failure` handler has wrong type hint

**Location:** `src/dynamic_harness/cli/tui.py`, line 61

```python
def _on_failure(self, agent_id: str, fail: Failure) -> None:
```

The import is guarded by `TYPE_CHECKING` and imports `Failure` — but the non-type-checking import path has `from ..core.task import Failure` only for `TYPE_CHECKING` in the `cli/tui.py` file.

**Check:** Actually, looking more carefully at the imports:

```python
if TYPE_CHECKING:
    from ..core.task import Failure
```

Since `Failure` is only used as a type annotation, and Python 3.10+ supports `from __future__ import annotations`, this is technically fine — the annotation is a string at runtime. However, it's inconsistent with how `ReportPayload` is used: `ReportPayload` is used in `_on_report` which is registered with `runtime.on_report(self._on_report)`, but `runtime.on_report` expects `Callable[[str, ReportPayload], None]`. The `ReportPayload` class is not imported at all in `tui.py` — let me check...

Actually, `ReportPayload` is **not imported in tui.py at all** — neither from the regular imports nor from the TYPE_CHECKING block. The `_on_report` method uses `payload: ReportPayload` in its signature, which with `from __future__ import annotations` becomes a string. At runtime, Python never evaluates the annotation, so this doesn't crash. But it's not correct.

**Fix:** Add `ReportPayload` to the `TYPE_CHECKING` block's imports.

---

## ⚠️ Moderate Issues

### 3. `Agent(ABC)` declares itself abstract but has no abstract methods

**Location:** `src/dynamic_harness/core/agent.py`, line 33

```python
class Agent(ABC):
```

Using `ABC` without any `@abstractmethod` is a no-op. The class can be instantiated directly. While the design intends users to subclass `Agent`, the `ABC` base class doesn't enforce this. 

Either remove `ABC` (since `run()` has a concrete default implementation) or make `run()` an abstract method (but then the default no-LLM behavior would need to live elsewhere).

**Recommendation:** Remove `ABC` — it's misleading as-is.

### 4. No `.gitignore` — `__pycache__` directories are tracked

**Location:** Root

The repository has build artifacts (`__pycache__`, `.pyc` files) in the source tree. There's no `.gitignore` to exclude them. If this is a git repository, these should be ignored.

### 5. `abc` imported but unused

**Location:** `src/dynamic_harness/core/agent.py`, line 4

```python
from abc import ABC
```

`ABC` is used on line 33, so this is fine.

But `ABC` isn't really doing anything useful here — see point 3.

### 6. `_tool_ask` uses blocking `input()` in REPL, overridden in TUI

**Location:** `src/dynamic_harness/core/capabilities.py`, lines 203-206

```python
async def _tool_ask(*, agent: Agent, question: str) -> str:
    loop = asyncio.get_event_loop()
    answer = await loop.run_in_executor(None, lambda: input(f"\n[Agent asks] {question}\nYour response: "))
    return answer.strip()
```

This is overridden in `tui.py` with a `Prompt.ask()` version. However, the override **registers a new handler under the same tool name** (`"ask"`), which replaces the original in the registry dict. This works but is fragile — if the order changes or if the registry prevents overwriting, it would break.

**Recommendation:** Consider having the tools accept an optional "ask handler" callback at construction time, rather than overwriting the registry entry.

### 7. `spawn()` always sync — parent blocks

**Location:** `src/dynamic_harness/core/capabilities.py`, lines 179-182

```python
async def _tool_spawn(*, agent: Agent, description: str) -> str:
    child = agent.spawn(description)
    await child.run()
    return f"Spawned agent completed..."
```

This is intentional per the design doc ("When you call spawn(), the sub-agent runs immediately"), but it means for deep trees the runtime is sequential. If the LLM wants to spawn 3 sub-agents, they run one after another, not in parallel.

**Recommendation:** The `run()` method or the tool could support parallel spawning via `asyncio.gather()`. This could be an optional behavior driven by the LLM asking for parallel execution.

### 8. Branch support in Repository is dead code

**Location:** `src/dynamic_harness/memory/repository.py`

The `Commit` model has a `branch` field (`branch: str = "main"`) and `Repository.log()` filters by branch. However, there are no branching operations (create branch, merge, rebase, checkout). The field is unused in practice.

**Recommendation:** Either remove it until branching is implemented, or add basic branching operations.

---

## 🔧 Minor Issues & Improvements

### 9. `tool_call_id` is not preserved in `ToolResult`

**Location:** `src/dynamic_harness/core/capabilities.py`, `ToolResult` class

The `ToolResult` has `tool_call_id` but it's passed to the LLM response format properly. This is fine.

Actually looking more carefully — the `ToolCall` model has `id` but it's not passed through. Let me check... The `execute` method receives `tool_call_id` and passes it to `ToolResult`. Then `results` dicts include `tool_call_id`. This looks correct.

### 10. Default persistence uses temp dirs — data lost between sessions

**Location:** `src/dynamic_harness/cli/tui.py` and `repl.py`

When `--temp` is not passed, the code uses `~/.dynamic-harness/`. But the default in single-shot mode (`repl.py`) uses temp dirs. The TUI uses persistent dirs by default, which is better.

**Recommendation:** The default should always be `~/.dynamic-harness/` unless `--temp` is explicitly passed.

### 11. `ReportPayload.summary` is truncated inconsistently

**Location:** `src/dynamic_harness/core/runtime.py`, lines 79-83

```python
view = ArtifactView(
    headline=payload.summary[:200] if payload.summary else "",
    summary_200=payload.summary[:200],
    summary_1000=payload.summary[:1000],
)
```

If `payload.summary` has 250 characters, `headline` and `summary_200` will both be the same (200 chars). If it has 500 chars, `summary_200` and `headline` are the same, while `summary_1000` has more.

This means `headline` and `summary_200` are never different. The progressive disclosure is flattened.

**Recommendation:** Generate actual hierarchical summaries:
- `headline`: first sentence or ~100 chars)
- `summary_200`: first ~200 chars or a generated short summary
- `summary_1000`: first ~1000 chars
- `technical` / `full_report`: the full content

Or, better yet, use the LLM to generate proper summaries at each level.

### 12. `_on_report` in TUI references `ReportPayload` without importing it

**Location:** `src/dynamic_harness/cli/tui.py`, line 55

```python
def _on_report(self, agent_id: str, payload: ReportPayload) -> None:
```

`ReportPayload` is not imported. Thanks to `from __future__ import annotations`, this works at runtime (annotations are strings), but type checkers will complain.

**Same issue** in `repl.py`, line 40.

### 13. `glob` module name collision

**Location:** `src/dynamic_harness/core/capabilities.py`, line 159

```python
import glob as _glob
```

This shadows the top-level `glob` import. It works because it's an alias, but it's confusing. The module should probably be `import glob` at the top level to avoid confusion with the tool name "glob".

Actually, the `glob` tool is defined as a function `_tool_glob`, so there's no collision. But `import glob as _glob` inside the function is unusual. Better to import at the top of the file.

### 14. `_load_existing` uses `rglob("commit.json")` — potentially slow

**Location:** `src/dynamic_harness/memory/repository.py`, lines 35-39

```python
def _load_existing(self) -> None:
    for p in self.root.rglob("commit.json"):
        data = p.read_text()
        c = Commit.model_validate_json(data)
        self._commits[c.id] = c
```

For large repositories with thousands of commits, this could be slow. The directory structure `{root}/{first2}/{commit_id}/commit.json` is designed for efficient lookup, but loading doesn't use it.

**Recommendation:** Store a manifest or index file (`index.json`) with all commit IDs and load from that, rather than scanning the filesystem.

### 15. Runtime's `reset()` doesn't reset Repository or ArtifactStore

**Location:** `src/dynamic_harness/core/runtime.py`, lines 124-127

```python
def reset(self) -> None:
    self._agents.clear()
    self._task_graph.clear()
```

This clears agents and the task graph, but the Repository and ArtifactStore retain their data. For a full reset, these should also be cleared (or the method should document that only the in-memory state is reset).

### 16. `_task_graph` is a flat dict — could be confused by re-used IDs

**Location:** `src/dynamic_harness/core/runtime.py`

```python
self._task_graph: dict[str, list[str]] = {}
```

Agent IDs are UUID hex strings (12 chars), unique per agent. This is fine. But `task_graph` is also an independent data structure from the `Repository.tree()` — the runtime maintains its own graph separately from the commit tree. These can drift apart if not kept in sync.

### 17. No type annotations on several method signatures

Minor issues found:
- `_tool_glob` uses `import glob as _glob` inside the function body
- `_tool_webfetch` imports `httpx` inside the function
- Several `Any` annotations could be more specific

### 18. `_build_runtime` is duplicated in `tui.py` and `repl.py`

**Location:** Both `src/dynamic_harness/cli/tui.py` and `src/dynamic_harness/cli/repl.py`

The `_build_runtime` function is nearly identical in both files. This is a code duplication that should be factored out into a shared utility.

---

## ✅ Things Done Well

1. **Clean separation of concerns:** Agent, Runtime, ArtifactStore, Repository — each has a single responsibility.

2. **Faithful to the design vision:** The code genuinely implements strict encapsulation (no sibling/sibling visibility), artifact-based communication, and Git-like provenance.

3. **Excellent test coverage:** Tests cover agent hierarchy, failure modes, tool execution, artifact persistence, and repository operations.

4. **Progressive disclosure:** Artifact views (headline → summary → full report) are well-designed.

5. **TUI is well-built:** Live tree rendering, event logging, and session history make a polished UX.

6. **Structured tool definitions:** Using Pydantic `BaseModel` for `ToolDef`, `ToolCall`, etc., with OpenAI-compatible schema generation.

7. **No code generation:** The tool loop is purely structured function calls — a clean and secure design choice.

8. **Python 3.10+ good practices:** Uses `from __future__ import annotations`, type hints, dataclasses/Pydantic models properly.

---

## 📋 Summary of Recommendations by Priority

### Must Fix
1. **`run()` doesn't stop on `report()`/`fail()`/`escalate()`** — Add status check after each tool call in the loop
2. **Missing `ReportPayload` import in TUI/REPL** — Add proper type-checked imports

### Should Fix
3. **`ABC` on Agent is misleading** — Remove it or make it truly abstract
4. **Add `.gitignore`** — Exclude `__pycache__`, `.pyc`, `venv/`
5. **Deduplicate `_build_runtime`** — Factor into shared module
6. **Parallel spawn support** — Allow the LLM to request concurrent sub-agents
7. **Index file for Repository** — Speed up loading with a manifest

### Nice to Have
8. **Generate hierarchical summaries properly** — Use LLM or NLP for views
9. **Branch operations** — Add merge/rebase/checkout to Repository, or remove `branch`
10. **Ask-tool override** — Use injection rather than registry overwriting
11. **Default to persistent storage** — Use `~/.dynamic-harness/` by default
12. **Full `reset()`** — Also clear Repository/ArtifactStore
13. **Top-level imports in capabilities** — Move inline imports to file top level