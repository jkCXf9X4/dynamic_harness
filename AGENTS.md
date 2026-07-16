---
title: "Dynamic Harness — AI Agent Onboarding"
category: meta
summary: >
  Structured reference for AI coding agents. Contains project overview,
  architecture, key files, data models, tools, conventions, and extension
  points. Read this first before making any changes.
model_refs:
  - Task, TaskStatus, ReportPayload, Escalation, Failure, DelegateRequest, BudgetRequest
  - Agent, Runtime, ToolRegistry, ToolDef, ToolCall, ToolResult
  - ArtifactView, Artifact, ArtifactStore
  - Commit, Repository
  - LLMProvider, LLMConfig, LLMResponse, ToolCallData, ToolCallResponse
  - AgentRunner, TraceStore
api_modules:
  - dynamic_harness.core.task
  - dynamic_harness.core.agent
  - dynamic_harness.core.runtime
  - dynamic_harness.core.capabilities
  - dynamic_harness.core.runner
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
├── __init__.py              → exports TraceStore
├── __main__.py              → entry: python -m dynamic_harness
├── core/
│   ├── agent.py             → Agent class + AGENT_SYSTEM_PROMPT + run() loop
│   ├── capabilities.py      → ToolDef, ToolCall, ToolRegistry, 15 tool implementations
│   ├── runtime.py           → Runtime orchestrator (agents, task graph, event handlers)
│   ├── task.py              → Task, ReportPayload, Escalation, Failure, DelegateRequest
│   ├── runner.py            → AgentRunner (pure lifecycle, no rendering)
│   └── trace.py             → TraceStore (JSONL debug trace)
├── cli/
│   ├── tui.py               → Textual TUI (main CLI, interactive REPL)
│   ├── common.py            → workspace_dir(), build_runtime()
│   └── agent_loop.py        → AgentLoop (Rich Live-rendered loop)
├── artifact/
│   ├── store.py             → ArtifactView, Artifact, ArtifactStore (progressive disclosure)
│   └── summary.py           → summarize_artifact(), hierarchical_summary()
├── memory/
│   └── repository.py        → Commit, Repository (Git-like provenance)
└── llm/
    ├── provider.py           → LLMProvider (ABC), LLMConfig, ToolCallResponse
    └── openai_provider.py    → OpenAIProvider (OpenAI/OpenRouter compatible)

tests/
├── test_agent.py             → Agent hierarchy, failure, report, sibling isolation
├── test_agent_loop.py        → AgentRunner completion, events, cancellation
├── test_agent_loop_detection.py → Safety: max iterations, repeated-call detection
├── test_runtime.py           → Runtime task graph, artifacts, event handlers
├── test_capabilities.py      → ToolRegistry + all 15 tool implementations
├── test_artifact.py          → ArtifactStore progressive disclosure, file I/O
└── test_repository.py        → Repository commits, parent/child, persistence

docs/
├── VISION.md                 → Architectural vision and success criteria
├── agent_methodology_guidelines.md → Mandatory agent workflow and anti-patterns
├── AGENTS.md                 → This file
├── api/                      → Module-level API reference
├── guides/                   → How-to guides for common workflows
└── concepts/                 → Architectural deep-dives
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
    summary: str         # Concrete findings (1-2 sentences)
    confidence: float | None  # 0.0–1.0
    claims: list[str]
    next_actions: list[str]
    artifact_ids: list[str]  # Paths/files written to disk
    questions: list[str]
)
```

### Agent (`core/agent.py`)
- Constructor: `Agent(agent_id, task, runtime, parent=None, system_prompt=None, safety_max_iterations=500, repeated_call_limit=5)`
- `async run()` — executes tool-calling loop to completion
- `delegate(description, role=None, system_prompt=None, **metadata)` — creates child Agent
- `report(payload: ReportPayload)` — delivers report to Runtime
- `escalate(issue, **context)` — escalates to parent
- `fail(error, trace=None)` — reports failure
- `continue_with_input(user_message)` — resumes agent with new input

### Runtime (`core/runtime.py`)
- Constructor: `Runtime(artifact_root, repo_root, trace_root=None, generated_root=None)`
- `delegate(task, parent=None, agent_type=None)` → Agent
- `deliver_report(agent_id, payload)` — save artifact + commit + fire handlers
- `deliver_escalation(agent_id, esc)` — mark task escalated
- `deliver_failure(agent_id, fail)` — mark task failed
- Event handlers: `on_report()`, `on_escalation()`, `on_failure()`, `on_budget_request()`
- `register_agent_class(name, cls)` — register custom agent type
- `set_llm(llm)` — inject LLM provider
- `task_graph()` → dict[str, list[str]] — parent→children map
- `reset()` — clear all state

### ToolRegistry (`core/capabilities.py`)
- `register(tool_def: ToolDef, fn: ToolFunc)` — add a tool
- `execute(name, tool_call_id, agent, **kwargs)` → ToolResult
- `openai_schemas()` → list[dict] — OpenAI function-calling format
- `list_tools()` → list[str]

### ArtifactView / Artifact / ArtifactStore (`artifact/store.py`)
- `ArtifactView(headline, summary_200, summary_1000, technical, full_report, raw_data)`
- `Artifact(id, task_id, agent_id, views, created_at, path)`
- `ArtifactStore(root)` — save/get/write_text/read_text/list_files

### Commit / Repository (`memory/repository.py`)
- `Commit(id, task_id, agent_id, summary, artifact_ids, parent_ids, child_ids, timestamp)`
- `Repository(root)` — commit/get/log/tree/count/clear, persisted as sharded JSON

### LLMProvider (`llm/provider.py`)
- `LLMProvider` (ABC) with `generate()`, `generate_with_tools()`, `generate_structured()`
- `LLMConfig(model, temperature, max_tokens)`
- Default implementation: `OpenAIProvider` in `llm/openai_provider.py`

## 15 Built-in Tools

| # | Tool | Parameters | Terminal? |
|---|------|-----------|-----------|
| 1 | `read` | `path: str` | No |
| 2 | `write` | `path: str, content: str` | No |
| 3 | `glob` | `pattern: str` | No |
| 4 | `grep` | `pattern: str, include?: str, path?: str` | No |
| 5 | `bash` | `command: str, timeout?: int` | No |
| 6 | `webfetch` | `url: str` | No |
| 7 | `edit` | `path: str, old_string: str, new_string: str` | No |
| 8 | `delegate` | `description: str, role?: str, system_prompt?: str` | No |
| 9 | `report` | `summary: str, artifact_ids?: list[str], confidence?: float` | **Yes** |
| 10 | `escalate` | `issue: str` | **Yes** |
| 11 | `fail` | `error: str` | **Yes** |
| 12 | `ask` | `question: str` | No |
| 13 | `compress` | *(none)* | No |
| 14 | `converse` | `agent_id: str, message: str` | No |
| 15 | `read_artifact` | `artifact_id: str` | No |

Terminal tools (report, escalate, fail) stop the agent loop.

## Safety Invariants

All safety mechanisms are in `Agent._run_loop()`:

1. **Max iterations:** Default 500. Exceeding → force-fail with message.
2. **Repeated-call detection:** 5 identical batches in a row → force-fail (prevents LLM loops).
3. **Context observation:** Every turn includes turn count, message count, token estimate.
4. **Compress tool:** LLM can compress its own context when past ~50 messages.

## Conventions for Modifying This Codebase

- **All Python files** use `from __future__ import annotations` + type hints
- **Pydantic models** for all data structures; never raw dicts
- **Async-first:** all agent execution is `async def`
- **UUID-based IDs:** 12-char hex prefixes via `uuid4().hex[:12]`
- **Tests** use `pytest` + `pytest-asyncio`; mock LLM providers for determinism
- **New tools** are registered via `register_default_tools()` in `capabilities.py`
- **New CLI commands** go in `cli/tui.py`
- Run tests: `pytest` from repo root

## Extension Points

| What | How |
|------|-----|
| Custom tool | `runtime.tool_registry.register(ToolDef(...), async fn)` |
| Custom agent class | Subclass `Agent`, register via `runtime.register_agent_class("name", cls)` |
| Custom LLM provider | Implement `LLMProvider` ABC |
| Event handlers | `runtime.on_report(fn)`, `runtime.on_escalation(fn)`, etc. |
| Programmatic usage | Import `Runtime` + `Task`, use `runtime.delegate()` + `agent.run()` |

## File-Search Quick Reference

| Need | Look in |
|------|---------|
| Add/modify a tool | `core/capabilities.py` |
| Change agent behavior | `core/agent.py` (AGENT_SYSTEM_PROMPT or _run_loop) |
| Change runtime lifecycle | `core/runtime.py` |
| Change data models | `core/task.py` |
| Change artifact storage | `artifact/store.py` |
| Change commit/persistence | `memory/repository.py` |
| Change LLM integration | `llm/openai_provider.py` |
| Change TUI interface | `cli/tui.py` |
| Change agent methodology | `docs/agent_methodology_guidelines.md` |