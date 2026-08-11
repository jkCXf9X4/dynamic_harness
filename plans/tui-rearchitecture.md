# Plan: Re-architect the Textual TUI (Option A)

> **Decided:** Keep Textual and re-architect, rather than consolidating to one Rich UI or dropping the TUI.
> **Goal:** Cut the recurring "multiple iterations to get text/views right" by removing the two root causes — duplicated rendering logic and UI/runtime coupling — and making rendering unit-testable.

---

## Root causes being addressed

- **Two parallel UIs with duplicated rendering logic**: `tui.py` (`_update_tree`, `_fmt_usage`) vs `terminal.py` (`_make_tree`, `_make_status`) each build the same tree/status independently.
- **Inconsistent truncation**: `[:40]`, `[:46]`, `[:50]`, `[:60]` scattered across both files.
- **UI tightly coupled to runtime internals**: `TUI` reads `task_graph()`, `all_agents()`, `get_usage()` directly and wires `on_report`/`on_activity` lambdas straight into `write_output`.
- **Accumulating duplicate event handlers**: handlers are re-registered inside every `_run_agent` call (latent bug).
- **Zero rendering tests**: only `tests/cli/test_tui_args.py` tests arg-parsing.
- **Dependency drift**: `pyproject.toml` allows `textual>=0.40` but **8.2.8** is installed; APIs may have shifted, contributing to flakiness.
- Existing good precedent: `format_event.py` already extracts a single source of event→text.

---

## 1. New pure view-model layer — `src/dynamic_harness/cli/present.py`

Pure, dependency-free data builders (no Textual/Rich imports, no async; `Runtime` is the only input). Single source of truth for **what** to show.

- `AgentNode` dataclass: `(id, description, status, tokens, messages, children: list[AgentNode])`
- `build_agent_tree(runtime) -> list[AgentNode]` — walks `task_graph()` / `all_agents()` / `get_usage()` into nested nodes (replaces `tui._update_tree` + `terminal._make_tree`).
- `build_stats(runtime) -> Stats(agents, commits, tokens)` (replaces `tui._refresh` stats + `terminal._make_status`).
- Centralized truncation constants: `ID_CHARS=8`, `DESC_CHARS`, `TREE_DESC_CHARS` — one place, no more `[:40]/[:46]/[:50]` scatter.

**Why:** pure logic is trivially testable; `tui.py` and `terminal.py` both consume it, eliminating duplication.

## 2. Rendering adapters — `src/dynamic_harness/cli/render.py`

Thin adapters mapping the model → each engine:
- `render_tree(...)` → Rich `Tree` (terminal)
- `apply_tree(textual_tree, model)` → Textual nodes (TUI)
- `render_event(event) -> str|None` (wraps existing `format_event.py`)
- `render_stats(...)` for both

Only this module knows about view styling/colors; the model stays engine-agnostic.

## 3. Decouple & rewire `src/dynamic_harness/cli/tui.py`

- Wire runtime event handlers **once** via a `_wire_events()` helper (currently re-registered per run — a latent duplicate-handler bug).
- Replace the 0.5s `_refresh` poll with mutation-driven updates: rebuild tree on activity/report/failure/usage events using `build_agent_tree`.
- `_update_tree` → `_apply_tree(model)`; drop duplicated logic; keep only widget interaction.
- Delegate agent *execution* stays as-is (`AgentRunner.run`); the App receives runtime data through `present.py`, not direct interleaving.

## 4. Unify `src/dynamic_harness/cli/terminal.py`

- `_make_tree` / `_make_status` / `_run_with_live` switch to `present.py` + `render.py`.
- Result: the same truncation and shaping rules render identically in both UIs.

## 5. Dependencies — `pyproject.toml`

- Pin `textual>=8.0` (installed **8.2.8**; currently allowed as low as 0.40 — likely source of API drift). Verify `Tree` / `RichLog` / `Tree.expand()` APIs against 8.x and fix any breakage.
- Align `rich>=15` to the installed version.

## 6. Tests — `tests/cli/`

- `test_present.py`: assert `build_agent_tree` nesting, ordering, description truncation, zero-parent root detection, and `build_stats`.
- Keep `test_tui_args.py`; add a headless Textual smoke test (`app.run_test()`) asserting the app composes and `apply_tree` renders without error.
- Optionally `test_render.py` for event-line rendering.

## 7. Docs

- Update `docs/guides/getting-started.md` TUI section if layout/commands change; note rendered output now comes from a single view-model source.

---

## Verification

- `pytest` from repo root (and the `tests/cli` dir first).
- Manual `dynamic-harness --tui --no-llm` to eyeball layout.

## Scope

- Keep the TUI's current feature set (tree sidebar, RichLog output, input box, `/commands`) and only rewire rendering — no user-facing feature loss.
