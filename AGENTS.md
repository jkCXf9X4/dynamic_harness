---
title: "Dynamic Harness — AI Agent Onboarding"
category: meta
summary: >
  Structured reference for AI coding agents. Contains project overview,
  architecture, key files, data models, tools, conventions, and extension
  points. Read this first before making any changes.
model_refs:
  - Task, TaskStatus, ReportPayload, Escalation, Failure, BudgetRequest, AgentOutcome
  - Agent, Runtime, ToolRegistry, ToolDef, ToolResult, ToolContext
  - ArtifactView, Artifact, ArtifactStore
  - Commit, Repository
  - LLMProvider, LLMConfig, LLMResponse, ToolCallData, ToolCallResponse
  - TraceStore
api_modules:
  - dynamic_harness.core.task
  - dynamic_harness.core.agent
  - dynamic_harness.core.context
  - dynamic_harness.core.environment
  - dynamic_harness.core.prompts
  - dynamic_harness.core.tool_context
  - dynamic_harness.core.runtime
  - dynamic_harness.core.tools.registry
  - dynamic_harness.core.events_format
  - dynamic_harness.core.telemetry
  - dynamic_harness.artifact.store
  - dynamic_harness.artifact.summary
  - dynamic_harness.memory.repository
  - dynamic_harness.llm.provider
  - dynamic_harness.llm.openai_provider
---

# Dynamic Harness — Project Reference for AI Agents

## Project Identity

**Name:** Dynamic Harness
**Language:** Python 3.10+
**Paradigm:** Async actor-model agent runtime with LLM tool-calling
**Author:** Erik Rosenlund
**License:** MIT

## What It Does

A recursive agent runtime that maximizes LLM output quality while minimizing cost. Agents use structured tool calls (not code generation) orchestrated by a central **Runtime**. Parent agents decompose work, delegate to children, verify output, and synthesize results — all with fresh isolated contexts.

**Key insight:** A 3-turn sub-agent with a clean slate outperforms a 20-turn monolithic agent.

## Directory Map

```
src/dynamic_harness/
├── __init__.py              → exports Harness + TraceStore
├── __main__.py              → entry: python -m dynamic_harness (prompt-only terminal CLI)
├── config.py                → HarnessConfig, LLMProviderConfig, SafetyConfig, harness.json loading
├── api/
│   └── harness.py           → Harness (high-level programmatic Python API)
├── core/
│   ├── agent.py             → Agent class + AGENT_SYSTEM_PROMPT + run() loop + outcome
│   ├── context.py           → AgentContext (turns, prune/restore/compress)
│   ├── environment.py       → EnvironmentInfo (runtime-detected, injected)
│   ├── references.py        → Reference library: discover + index durable rationale docs
│   ├── tool_context.py      → ToolContext (public interface handed to tool functions)
│   ├── runtime.py           → Runtime orchestrator (agents, task graph, event bus, run())
│   ├── task.py              → Task, ReportPayload, Escalation, Failure, AgentOutcome, ActivityEvent
│   ├── events.py            → EventBus (isolated handler dispatch)
│   ├── events_format.py     → format_event() — single event→text source
│   ├── usage.py             → UsageTracker (per-agent/total token tracking)
│   ├── trace.py             → TraceStore (JSONL debug trace)
│   ├── telemetry.py         → Telemetry (per-agent facade isolating the run loop from usage/trace/activity/checkpoint I/O)
│   ├── checkpoint.py        → AgentCheckpoint + CheckpointStore (plan/progress persisted to JSON for resumability)
│   ├── policies/             → composable, host-agnostic decision objects (LoopGuard, SpawnPolicy, HealPolicy, AgentPolicy, RetryPolicy, DisclosurePolicy, …) wire into agent/runtime/tools
│   │   ├── interface.py       → shared metric-reactive contract: Observation → PromptInjection via ReactivePolicy + ReactivePolicyRegistry
│   │   └── …                  → each policy is host-agnostic (no agent/runtime import)
│   └── tools/               → ToolDef/ToolResult/ToolRegistry + 25 tools split by concern
│       ├── registry.py      → ToolRegistry (register/execute/openai_schemas, builds ToolContext)
│       ├── registration.py  → register_default_tools()
│       ├── filesystem.py    → read, write, glob, grep, edit (+ sandbox helpers)
│       ├── process.py       → bash
│       ├── network.py       → webfetch
│       ├── agents.py        → delegate, report, escalate, fail, ask, converse, read_artifact
│       ├── planning.py      → plan, checkpoint
│       └── context.py       → compress, prune, restore
├── cli/
│   ├── terminal.py          → DEFAULT CLI: prompt-only (batch, -i REPL); outcome printed
│   ├── present.py           → AgentNode/Stats view-models + render_text_tree (pure text)
│   ├── state.py             → StateWriter: persists agents.txt / agent_tree.json / stats.json / events.jsonl
│   └── common.py            → workspace_dir(), build_runtime()
├── artifact/
│   ├── store.py             → ArtifactView, Artifact, ArtifactStore (progressive disclosure)
│   └── summary.py           → summarize_artifact(), hierarchical_summary()
├── memory/
│   └── repository.py        → Commit, Repository (Git-like provenance)
├── benchmark/               → BenchmarkTask suite + deterministic scoring/verification
│   ├── tasks.py             → ALL_TASKS (single canonical task source)
│   ├── runner.py, scoring.py, metrics.py, report.py
│   └── run.py               → standalone CLI (python -m dynamic_harness.benchmark.run)
└── llm/
    ├── provider.py           → LLMProvider (ABC), LLMConfig, LLMResponse, ToolCallData, ToolCallResponse
    └── openai_provider.py    → OpenAIProvider (OpenAI/OpenRouter compatible)

tests/
├── backend/
│   ├── test_agent.py             → Agent hierarchy, failure, report, sibling isolation
│   ├── test_agent_loop.py        → Runtime.run() completion, events, cancellation
│   ├── test_agent_loop_detection.py → Safety: max iterations, repeated-call detection
│   ├── test_runtime.py           → Runtime task graph, artifacts, event handlers, provenance
│   ├── test_capabilities.py      → ToolRegistry + all 17 tool implementations
│   ├── test_tool_interaction.py  → tool-level behavior (read/write/grep/glob/compress/prune/…)
│   ├── test_artifact.py          → ArtifactStore progressive disclosure, file I/O
│   ├── test_repository.py        → Repository commits, parent/child, persistence
│   ├── test_e2e.py               → end-to-end report flows with rich views
│   └── test_benchmark.py         → scoring/aggregation
└── cli/
    ├── test_present.py           → build_agent_tree / build_stats view-models
    └── test_state.py             → StateWriter JSON + events.jsonl persistence

docs/
├── VISION.md                 → Architectural vision and success criteria
├── requirements.md           → CLI direction & requirements (prompt-only + persisted overview)
├── agent_methodology_guidelines.md → Mandatory agent workflow and anti-patterns
├── AGENTS.md                 → This file
├── references/               → Durable rationale library that survives prompt optimization
│   ├── 15288_rationale.md    → Why the lifecycle / V-model / artifact-driven design
│   ├── tool_motivations.md   → Why each tool exists + how to choose between them
│   ├── guidelines.md         → Delegation / verification / stopping-conditions nuance
│   └── mission_command_rationale.md → Uppdragstaktik (mission command): why delegation briefs must carry intent, end state, constraints, and freedom of action
├── api/                      → Module-level API reference
│   ├── config.md             → Every harness.json setting (defaults + 0/null "cap off" convention)
├── guides/                   → How-to guides for common workflows
│   (performance-diagnostics.md → scaling profiler + methodology for slowdowns)
├── gap-analysis.md           → Evaluation: concept/use-case promises vs implementation (G1–G13)
├── concepts/                 → Architectural deep-dives
│   ├── agent-lifecycle.md
│   ├── artifact-system.md
│   ├── delegation-model.md
│   └── self-healing.md        → Layered failure-recovery policy (resume / fresh / escalate)
└── use-cases/                 → Plausible use-cases deduced from the concepts + runtime
    ├── index.md               → Taxonomy + fitness filter + how to read each family
    ├── repository-analysis.md → Inventory, audit, security, debt scanning
    ├── change-and-validation.md → Bug fix, test coverage, refactor, codegen
    ├── documentation-and-knowledge.md → Module docs, reference-library curation, overviews
    ├── research-and-synthesis.md → External research with cited artifacts
    ├── pipelines-and-jobs.md  → Batch extraction + long resumable jobs
    ├── evaluation-and-qa.md   → Benchmark suite, prompt A/B, failure triage
    └── embedding-and-integration.md → Library use, custom agents/tools, product workflows
```

## Architecture Principles

1. **Actor model** — Agents are isolated; know only parent + children + task
2. **Runtime/graph separation** — Runtime owns the task graph; agents never see it
3. **Artifact-driven communication** — Findings → disk; parents consume summaries
4. **Progressive disclosure** — Headline → 200-char → 1000-char → technical → full
5. **Disposable workers** — State lives in immutable artifacts, not agent memory
6. **Git-like provenance** — Every completed task creates a Commit
7. **Fresh context economics** — Delegation overhead (~3K tokens) < context rot

## Core Data Flow

```
User/CLI → Runtime.delegate(Task) → Agent.run()
  │                                      │
  │                                      ├── _run_loop()
  │                                      │   ├── LLM.generate_with_tools()
  │                                      │   ├── ToolRegistry.execute()
  │                                      │   └── loop until report/escalate/fail
  │                                      │
  │                                      ├── delegate() → child Agent.run()
  │                                      │                   └── (recursive)
  │                                      │
  │                                      └── report(ReportPayload)
  │                                            │
  │                                            ▼
  └─────────────────────────── Runtime.deliver_report()
                                  ├── ArtifactStore.save()
                                  ├── Repository.commit()
                                  └── Fire report_handlers[]
```

## Key Models (Pydantic)

### Task (`core/task.py`)
```python
Task(
    id: str            # uuid4 hex, 12 chars
    description: str   # What the agent should do
    role: str | None   # Scope constraint tag
    system_prompt: str | None  # Override default prompt
    parent_id: str | None
    status: TaskStatus # pending | running | completed | failed | escalated
    created_at: datetime  # UTC
    metadata: dict
)
```

### ReportPayload (`core/task.py`)
```python
ReportPayload(
    task_id: str
    summary: str              # Concrete findings (1-2 sentences)
    technical_summary: str | None  # Detailed technical analysis (optional)
    full_report: str | None   # Complete report with full detail (optional)
    confidence: float | None  # 0.0–1.0
    claims: list[str]
    next_actions: list[str]
    artifact_ids: list[str]   # Stored artifact UUIDs (system-managed)
    files_written: list[str]  # Files the agent wrote to disk
    questions: list[str]
)
```

### Agent (`core/agent.py`)
- Constructor: `Agent(agent_id, task, runtime, parent=None, *, system_prompt=None, safety_max_iterations=500, repeated_call_limit=5, safety_timeout_seconds=None, active_turn_window=50, max_pruned_retained=100, stream_children=False)`
- `async run()` — executes tool-calling loop to completion
- `stream_children: bool` — when True (default via `agent.stream_children` in `harness.json`), delegations are fire-and-forget and the parent is re-admitted to its loop as each child settles (`[child settled]` injected to its context), so it can act on child events (report/escalate/fail/ask) before siblings finish. Set `false` to restore the block-until-all gather.
- `delegate(description, role=None, system_prompt=None, **metadata)` — creates child Agent
- `report(payload: ReportPayload)` — delivers report to Runtime
- `escalate(issue, **context)` — escalates to parent
- `fail(error, trace=None)` — reports failure
- `continue_with_input(user_message)` — resumes agent with new input
- `request_more_budget(current_usage, requested, reason)` — emits budget request
- `get_other_agent(agent_id)` — look up another agent by ID

### Runtime (`core/runtime.py`)
- Constructor: `Runtime(artifact_root, repo_root, trace_root=None, generated_root=None, config=None)`
- Defaults: config is the single defaults provider — a bare `Runtime()` (or `Runtime(artifacts, repos, config=None)`) behaves exactly like a default `HarnessConfig()`. The old `if config else <n>` fallback ladder (with `900`/`True`/`25`/`15` literals) was removed; knobs like `safety.max_agent_tokens` simply stay `None` (uncapped) by default.
- `delegate(task, parent=None, agent_type=None)` → Agent
- `deliver_report(agent_id, payload)` — save artifact + commit + fire handlers
- `deliver_escalation(agent_id, esc)` — mark task escalated
- `deliver_failure(agent_id, fail)` — mark task failed
- Event handlers: `on_report()`, `on_escalation()`, `on_failure()`, `on_budget_request()`, `on_activity()`
- `register_agent_class(name, cls)` — register custom agent type
- `set_llm(llm)` — inject LLM provider
- `resume(agent_id, message=None)` — rebuild an interrupted/failed agent from its persisted checkpoint and continue it to completion
- `task_graph()` → dict[str, list[str]] — parent→children map
- `get_usage(agent_id)` / `total_usage()` — per-agent / aggregate token usage
- `reset(clear_handlers=False)` — clear state (event handlers only if `clear_handlers=True`)

### ToolRegistry (`core/tools/registry.py`)
- `register(tool_def: ToolDef, fn: ToolFunc)` — add a tool
- `execute(name, tool_call_id, agent, **kwargs)` → ToolResult (hands tools a `ToolContext`)
- `openai_schemas()` → list[dict] — OpenAI function-calling format
- `list_tools()` → list[str]

### Policy layer (`core/policies/`)
Config-sourced decision logic is extracted into host-agnostic policy objects
(`SpawnPolicy`, `HealPolicy`, `AgentPolicy`, `RetryPolicy`, `LoopGuard`,
`DisclosurePolicy`, `TimeoutPolicy`, `BashSafetyPolicy`, `BriefPolicy`, …). Each policy imports
neither an agent nor a runtime; **Runtime** / **Agent** / **ToolRegistry** now
delegate to them. This keeps the decision half reusable as a plugin surface
(e.g. an MCP server / extension boundary) — see `docs/platform-evaluation.md`.

### ArtifactView / Artifact / ArtifactStore (`artifact/store.py`)
- `ArtifactView(headline, summary_200, summary_1000, technical, full_report, raw_data)`
- `Artifact(id, task_id, agent_id, views, created_at, path)`
- `ArtifactStore(root)` — save/get/write_text/read_text/list_files

### Commit / Repository (`memory/repository.py`)
- `Commit(id, task_id, agent_id, summary, artifact_ids, parent_ids, child_ids, timestamp)`
- `Repository(root)` — commit/get/log/tree/count/clear, persisted as sharded JSON

### AgentCheckpoint / CheckpointStore (`core/checkpoint.py`)
- `AgentCheckpoint(agent_id, agent_type, session_id, task, focus, messages, checkpoint_notes, turn_counter, turn_order, turns, pruned, prune_markers, terminated)`
- `CheckpointStore(root)` — save(agent)/load(agent_id)/list/clear; persisted as JSON per agent
- The run loop auto-persists an `AgentCheckpoint` after every committed turn; `Runtime.resume(agent_id)` rebuilds a live agent from it.

### LLMProvider (`llm/provider.py`)
- `LLMProvider` (ABC) with `generate()`, `generate_with_tools()`, `generate_structured()`
- `LLMConfig(model, temperature, max_tokens, provider_ignore, provider_allow_fallbacks, provider_force)`
- Default implementation: `OpenAIProvider` in `llm/openai_provider.py`

## 26 Built-in Tools

Defined in `core/tools/` (definitions in each module, wired by `core/tools/registration.py`). Tool functions receive a `ToolContext` (never the Agent).

| # | Tool | Parameters | Terminal? |
|---|------|-----------|----------|
| 1 | `read` | `path: str` | No |
| 2 | `write` | `path: str, content: str` | No |
| 3 | `glob` | `pattern: str` | No |
| 4 | `grep` | `pattern: str, include?: str, path?: str` | No |
| 5 | `bash` | `command: str, timeout?: int` | No |
| 6 | `webfetch` | `url: str` | No |
| 7 | `edit` | `path: str, old_string: str, new_string: str` | No |
| 8 | `delegate` | `description: str, role?: str, system_prompt?: str, agent_type?: str` | No |
| 9 | `report` | `summary: str, artifact_ids?: list[str], technical_summary?: str, full_report?: str, confidence?: float` | **Yes** |
| 10 | `escalate` | `issue: str` | **Yes** |
| 11 | `fail` | `error: str` | **Yes** |
| 12 | `ask` | `question: str` | No |
| 13 | `compress` | *(none)* | No |
| 14 | `prune` | `prune_ids?: list[str]` | No |
| 15 | `restore` | `prune_id: str` | No |
| 16 | `converse` | `agent_id: str, message: str` | No |
| 17 | `kill` | `agent_id: str, reason?: str, recursive?: bool` | No |
| 18 | `status` | `agent_id?: str` | No |
| 19 | `resume` | `agent_id: str, note?: str, strategy?: str` | No |
| 20 | `read_artifact` | `artifact_id: str, file?: str, level?: str` | No |
| 21 | `plan` | `steps: list[str], objective?: str, acceptance?: list[str], deliverable?: str` | No |
| 22 | `checkpoint` | `note: str` | No |
| 23 | `usage` | *(none)* | No |
| 24 | `archive` | `content?: str, path?: str, label?: str, summary?: str` | No |
| 25 | `result_read` | `result_id: str, token_limit?: int, token_offset?: int` | No |
| 26 | `result_bash` | `result_id: str, command: str, timeout?: int` | No |

Terminal tools (report, escalate, fail) stop the agent loop. `plan` records the
agent's step decomposition (re-stated as progress each turn and persisted to its
checkpoint); `checkpoint` writes a milestone note to disk. `usage` returns the
agent's own cumulative message/token counts and live-context estimate so it can
self-regulate (no per-turn observation message — see Safety Invariants). `resume`
lets a parent recover a failed/under-delivered child: `automatic` diagnoses
blunt-vs-rot (resume the same child vs spawn a fresh worker), `resume` forces
same-child, `fresh` forces a clean restart; a parent `note` is appended as a
corrective instruction, and it shares the child's self-heal budget. The run
loop also auto-persists a structured `AgentCheckpoint` after every committed
turn, so an interrupted or failed task can be resumed from disk via
`Runtime.resume(agent_id)` (e.g. `--resume <id>` in the CLI) — state lives in
the immutable checkpoint, not only in agent memory. A timed-out child is never
auto self-healed (its context is intact — it is diagnosed **blunt**, not rot) —
the parent decides via `resume(agent_id, strategy="resume"|"fresh")` or
re-delegation; the failure message and `status` `heal.resume_hint` carry those
directions.

## Safety Invariants

All safety mechanisms are in `Agent._run_loop()`:

1. **Max iterations:** Default 400. Exceeding → force-fail with message.
2. **Repeated-call detection:** 5 identical batches in a row → force-fail (prevents LLM loops). Pure monitoring tools (`safety.repeated_call_exempt_tools`, default `status`, `usage`, `result_read`, `result_bash`) are excluded entirely — these are cheap read-only observations whose outputs change as live state changes, so a parent polling its running/self-healing children is waiting, not looping; a turn composed solely of them is not counted at all (genuinely stuck agents are still bounded by max_iterations / max_agent_tokens / timeout). **Near-identical warning + escalation:** when `<N` string-similar-but-not-identical `bash` commands recur inside a sliding window (`safety.near_identical_threshold`, default 3 in `near_identical_window` 6), a `[notice]` user message is injected telling the agent to use the `read` tool / raise `token_limit` / delegate / move on. Bash signatures are pagination-normalized (`sed -n 'A,Bp'` / `awk NR>=A&&NR<=B` / `head -N` collapse to a family) and *same-file overlapping ranges* are the primary repeat signal, so re-fetching the same lines through a different wrapper is caught while strictly-disjoint forward paging and different files stay silent. The budget (`safety.near_identical_warning_attempts`, default 2) is **per command family**, not global; a family that keeps re-reading the same material past its budget escalates into hard repeated-call detection (nudge via `safety.repeated_recovery_attempts`, default 2, then force-fail) instead of going silent. `token_offset`/`token_limit` are excluded from the signature so *read-style* paged reads are never flagged, and whitespace-only assistant responses are never counted as repeated text.

3. **Result caching (read-only):** every cacheable tool call (`read`, `glob`, `grep`, `bash`, `webfetch`, `read_artifact`, `status`, `usage`, `plan`, `checkpoint` — anything not in the mutator set `write`/`edit`/`delegate`/`report`/`escalate`/`fail`/`kill`/`ask`/`archive`/`prune`/`restore`/`compress`/`converse`/`resume`) stores its FULL output in a per-agent, bounded, in-memory `ResultStore` behind an opaque handle. When a result is truncated, the footer advertises the handle and the read-only `result_read` tool pages the snapshot by `result_id`, and `result_bash` pipes it to a shell command's **stdin** (so `rg`/`jq`/`awk`/`wc -l` etc. can probe an expensive cached result) — **never re-executing** the producing tool (so paging slow bash/webfetch is free). Handles are always read-only: getting a fresh result means calling the work tool again (work tools accept no `result_id` input). The store is memory-only and cleared on agent GC/reset, so a resumed agent never sees stale snapshots (an unknown handle errors with "re-run the producing tool").
4. **Wall-clock timeout:** `safety.timeout_seconds` (default 7200) → force-fail when exceeded. `safety.disable_root_timeout` (default true) exempts only the root. Timeouts are **never self-healed** — the child stays failed for the parent, who resumes it (`strategy="resume"` same context / `"fresh"` clean retry) or re-delegates.
5. **Token budget:** Optional `safety.max_agent_tokens` cap → force-fail when cumulative usage exceeds it.
6. **Context observation:** Kept static/cache-friendly — agents read their own live turn count, message count, and token estimates on demand via the `usage` tool instead of a changing per-turn message.
7. **Compress tool:** LLM can compress its own context when past ~50 messages.
8. **Prune/restore tools:** LLM can drop stale committed turns (`prune`) and recover them (`restore`).
9. **Delegation / spawn caps** (`Runtime.delegate()` copies, so every spawn — roots, children, self-heal fresh restarts — passes through the same gate):
   - `safety.max_agents` (default 300): total agents per runtime run. Reached → every further `delegate` is **refused** (never creates an agent).
   - `safety.max_depth` (default 15): tree depth; root = 0. Delegating past it is refused.
   - `safety.max_same_target_delegations` (default 0, cap off): per-lineage cap on re-delegating the same target — the target signature is the normalized file/directory path(s) in the description (canonical `delegate_target_signature` in `core/policies/spawn.py`, re-exported from `core/spawn_limits.py` for back-compat), shared down the whole family so re-spawning an identical 'explore the same repo' sub-agent over and over (even across self-heal restarts) trips it when the cap is set (`>0`). `0`/`null` disables the cap.
   - Refusals raise `DelegationLimit`; the `delegate` tool surfaces them to the model as a `status: refused` tool result (with a `[delegation budget]` line) plus a `safety_warning` activity. Every delegate result carries that budget line (agents spawned/depth/repeated target) so the model self-regulates.
   - Non-fatal `[notice]` injected when any cap is ≥80% used (`safety.spawn_limit_warning_attempts`, default 2).

## Process (CLI / programmatic)

- Default CLI = `cli/terminal.py` (prompt-only; batch + `-i` REPL prints the final outcome, and interactive sessions stream the root agent's text replies above the live prompt).
- The `agent_system_prompt.txt` is loaded at import time into `AGENT_SYSTEM_PROMPT`.
- Applies `harness.json` via `config.load_harness_config()`. Config is a layered deep-merge: the XDG user-global base (`~/.config/dynamic-harness/harness.json`) is applied first, then the local overlay (`./harness.json`, or explicit `--config`) overrides it per-key (sections merge field-by-field; scalars/lists replace wholesale). No files → defaults.
- No-LLM mode: without `set_llm()`, `Agent.run()` fails with "No LLM provider configured".

## Conventions for Modifying This Codebase

- **All Python files** use `from __future__ import annotations` + type hints
- **Pydantic models** for all data structures; never raw dicts
- **Async-first:** all agent execution is `async def`
- **UUID-based IDs:** 12-char hex prefixes via `uuid4().hex[:12]`
- **Tests** use `pytest` + `pytest-asyncio`; mock LLM providers for determinism
- **New tools** are registered via `register_default_tools()` in `core/tools/registration.py`
- **New CLI commands** go in `cli/terminal.py`
- Run tests: `pytest` from repo root

## Extension Points

| What | How |
|------|-----|
| Custom tool | `runtime.tool_registry.register(ToolDef(...), async fn)` |
| Custom agent class | Subclass `Agent`, register via `runtime.register_agent_class("name", cls)` |
| Custom LLM provider | Implement `LLMProvider` ABC |
| Event handlers | `runtime.on_report(fn)`, `runtime.on_escalation(fn)`, etc. |
| Custom timimg/policy decision | Construct one of the `core/policies/` objects (e.g. `SpawnPolicy`, `RetryPolicy`) and either pass it into `Runtime`/`ToolRegistry` or subclass the policy |
| Programmatic usage | Import `Runtime`, use `await runtime.run(description)` → `agent.outcome` |

## File-Search Quick Reference

| Need | Look in |
|------|---------|
| Add/modify a tool | `core/tools/` (registry + registration + per-concern module) |
| Add/modify a policy | `core/policies/` |
| Change agent behavior | `core/agent.py` (AGENT_SYSTEM_PROMPT or _run_loop) |
| Change runtime lifecycle | `core/runtime.py` |
| Change data models | `core/task.py` |
| Change artifact storage | `artifact/store.py` |
| Change commit/persistence | `memory/repository.py` |
| Change LLM integration | `llm/openai_provider.py` |
| Change terminal interface | `cli/terminal.py` |
| Change agent methodology | `docs/agent_methodology_guidelines.md` |
| Change rationale / reference library | `core/references.py` + `docs/references/` |



### Information Hygiene — Mandatory

* **Maintain canonical state, not historical accumulation.** Whenever information changes, **remove, replace, or supersede stale information**. Do not simply append new information on top of existing information.

* **Treat excessive information as an anti-pattern.** Unnecessary, redundant, outdated, or conflicting information increases cognitive load, slows development, and creates ambiguity. **Prefer the smallest set of information necessary to represent the current canonical state.**

* **Determine the canonical disposition before storing information.** For every piece of information, evaluate whether it should be **created, updated, replaced, merged, superseded, or removed**.

* **Prevent duplication and contradiction.** Before adding information, check whether an existing representation already covers it. Update the existing source of truth rather than creating another competing representation.

* **Do not preserve stale state by default.** Historical information should only be retained when it has an explicit purpose and a clearly defined place to live.

* **Optimize for future retrieval and action.** Information should be structured so an agent can quickly determine **what is current, what is authoritative, and what should be ignored**.
