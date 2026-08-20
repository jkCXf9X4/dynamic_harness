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
├── __main__.py              → entry: python -m dynamic_harness (Rich terminal CLI)
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
│   ├── checkpoint.py        → AgentCheckpoint + CheckpointStore (plan/progress persisted to JSON for resumability)
│   └── tools/               → ToolDef/ToolResult/ToolRegistry + 19 tools split by concern
│       ├── registry.py      → ToolRegistry (register/execute/openai_schemas, builds ToolContext)
│       ├── registration.py  → register_default_tools()
│       ├── filesystem.py    → read, write, glob, grep, edit (+ sandbox helpers)
│       ├── process.py       → bash
│       ├── network.py       → webfetch
│       ├── agents.py        → delegate, report, escalate, fail, ask, converse, read_artifact
│       ├── planning.py      → plan, checkpoint
│       └── context.py       → compress, prune, restore
├── cli/
│   ├── terminal.py          → DEFAULT CLI: Rich Live-rendered terminal (batch, -i REPL)
│   ├── present.py           → AgentNode/Stats view-models (build_agent_tree, build_stats)
│   ├── render.py            → Rich adapter over present.py
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
    └── test_present.py           → build_agent_tree / build_stats view-models

docs/
├── VISION.md                 → Architectural vision and success criteria
├── agent_methodology_guidelines.md → Mandatory agent workflow and anti-patterns
├── AGENTS.md                 → This file
├── references/               → Durable rationale library that survives prompt optimization
│   ├── 15288_rationale.md    → Why the lifecycle / V-model / artifact-driven design
│   ├── tool_motivations.md   → Why each tool exists + how to choose between them
│   └── guidelines.md         → Delegation / verification / stopping-conditions nuance
├── api/                      → Module-level API reference
├── guides/                   → How-to guides for common workflows
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
- `stream_children: bool` — when True, delegations are fire-and-forget and the parent is re-admitted to its loop as each child settles (`[child settled]` injected to its context), so it can act on child events (report/escalate/fail/ask) before siblings finish. Via `agent.stream_children` in `harness.json`. Default False preserves the block-until-all gather.
- `delegate(description, role=None, system_prompt=None, **metadata)` — creates child Agent
- `report(payload: ReportPayload)` — delivers report to Runtime
- `escalate(issue, **context)` — escalates to parent
- `fail(error, trace=None)` — reports failure
- `continue_with_input(user_message)` — resumes agent with new input
- `request_more_budget(current_usage, requested, reason)` — emits budget request
- `get_other_agent(agent_id)` — look up another agent by ID

### Runtime (`core/runtime.py`)
- Constructor: `Runtime(artifact_root, repo_root, trace_root=None, generated_root=None, config=None)`
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

## 20 Built-in Tools

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
| 17 | `read_artifact` | `artifact_id: str, file?: str, level?: str` | No |
| 18 | `plan` | `steps: list[str], objective?: str, acceptance?: list[str], deliverable?: str` | No |
| 19 | `checkpoint` | `note: str` | No |
| 20 | `usage` | *(none)* | No |

Terminal tools (report, escalate, fail) stop the agent loop. `plan` records the
agent's step decomposition (re-stated as progress each turn and persisted to its
checkpoint); `checkpoint` writes a milestone note to disk. `usage` returns the
agent's own cumulative message/token counts and live-context estimate so it can
self-regulate (no per-turn observation message — see Safety Invariants). The run
loop also auto-persists a structured `AgentCheckpoint` after every committed
turn, so an interrupted or failed task can be resumed from disk via
`Runtime.resume(agent_id)` (e.g. `--resume <id>` in the CLI) — state lives in
the immutable checkpoint, not only in agent memory.

## Safety Invariants

All safety mechanisms are in `Agent._run_loop()`:

1. **Max iterations:** Default 500. Exceeding → force-fail with message.
2. **Repeated-call detection:** 5 identical batches in a row → force-fail (prevents LLM loops). **Near-identical warning:** separate, *non-fatal* — when N string-similar-but-not-identical `bash` commands (e.g. re-listing the same paths with different head/tail/sed) recur inside a sliding window (`safety.near_identical_threshold`, default 3 in `near_identical_window` 6), a `[notice]` user message is injected telling the agent to paginate via `token_offset`/delegate/move on. It never fails the run; pagination knobs are excluded from the similarity signature so paged reads are never flagged.
3. **Wall-clock timeout:** Optional `safety_timeout_seconds` → force-fail when exceeded.
4. **Token budget:** Optional `safety.max_agent_tokens` cap → force-fail when cumulative usage exceeds it.
5. **Context observation:** Kept static/cache-friendly — agents read their own live turn count, message count, and token estimates on demand via the `usage` tool instead of a changing per-turn message.
6. **Compress tool:** LLM can compress its own context when past ~50 messages.
7. **Prune/restore tools:** LLM can drop stale committed turns (`prune`) and recover them (`restore`).

## Process (CLI / programmatic)

- Default CLI = `cli/terminal.py` (Rich Live-rendered, batch + `-i` REPL).
- The `agent_system_prompt.txt` is loaded at import time into `AGENT_SYSTEM_PROMPT`.
- Applies `harness.json` via `config.load_harness_config()` (discovery: `--config` → `./harness.json` → `~/.config/dynamic-harness/harness.json` → defaults).
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
| Programmatic usage | Import `Runtime`, use `await runtime.run(description)` → `agent.outcome` |

## File-Search Quick Reference

| Need | Look in |
|------|---------|
| Add/modify a tool | `core/tools/` (registry + registration + per-concern module) |
| Change agent behavior | `core/agent.py` (AGENT_SYSTEM_PROMPT or _run_loop) |
| Change runtime lifecycle | `core/runtime.py` |
| Change data models | `core/task.py` |
| Change artifact storage | `artifact/store.py` |
| Change commit/persistence | `memory/repository.py` |
| Change LLM integration | `llm/openai_provider.py` |
| Change terminal interface | `cli/terminal.py` |
| Change agent methodology | `docs/agent_methodology_guidelines.md` |
| Change rationale / reference library | `core/references.py` + `docs/references/` |