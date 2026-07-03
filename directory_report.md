# Project Report: `dynamic_harness`

## Overview

**`dynamic_harness`** is a **recursive agent harness** for building hierarchical, tool-calling AI agent systems. It is a Python package (v0.1.0, MIT License) by Erik Rosenlund, implementing a novel architecture inspired by the actor model, artifact-based communication, Git-like provenance, and strict information encapsulation.

The project files are located at: `src/dynamic_harness/`

---

## Directory Structure

```
.
├── LICENSE                          # MIT License
├── README.md                        # Project overview and documentation
├── pyproject.toml                   # Package config (dependencies, entry point)
├── starting_point.md                # Architectural inspiration (conversation with ChatGPT)
├── examples/                        # Example scripts
│   ├── __init__.py
│   ├── hierarchy_demo.py            # Demo of agent hierarchy with registered types
│   ├── openrouter_demo.py           # Demo using OpenRouter/deepseek LLM
│   └── research_agent.py            # Basic research agent demo
├── src/dynamic_harness/             # Main package source
│   ├── __init__.py
│   ├── __main__.py                  # Entry point → CLI repl
│   ├── core/                        # Core agent loop, tools, runtime, tasks
│   │   ├── __init__.py
│   │   ├── agent.py                 # Agent base class + tool-calling run() loop
│   │   ├── capabilities.py          # ToolDef, ToolRegistry, all tool implementations
│   │   ├── runtime.py               # Runtime (orchestrator, task graph, artifact store)
│   │   └── task.py                  # Task, ReportPayload, Escalation, Failure models
│   ├── artifact/                    # Artifact storage with progressive disclosure
│   │   ├── __init__.py
│   │   ├── store.py                 # ArtifactStore (persistence, views)
│   │   └── summary.py               # Hierarchical summarization helpers
│   ├── memory/                      # Git-like commit repository
│   │   ├── __init__.py
│   │   └── repository.py            # Repository (commits, tree, persistence)
│   ├── llm/                         # LLM provider abstraction
│   │   ├── __init__.py
│   │   ├── provider.py              # Abstract LLMProvider
│   │   └── openai_provider.py       # OpenAI/OpenRouter implementation
│   └── cli/                         # CLI / REPL
│       └── repl.py                  # Interactive CLI with Rich live display
└── tests/                           # Test files
    ├── __init__.py
    ├── test_agent.py
    ├── test_artifact.py
    ├── test_capabilities.py
    ├── test_repository.py
    └── test_runtime.py
```

---

## Architecture & Key Design Principles

### 1. Recursive Agent Hierarchy (Actor Model)
- Agents know only: their **task**, **parent**, and **children**.
- They have **no visibility** into siblings, cousins, or the global task graph.
- Communication flows **down** (parent spawns children) and **up** (children report to parent).

### 2. Tool-Calling Loop
- Each agent runs a loop: receives a task, calls tools, feeds results back, and eventually calls `report()`.
- Available tools: `read`, `write`, `glob`, `webfetch`, `edit`, `spawn`, `ask`, `report`, `escalate`, `fail`.
- **No code generation** — all interaction is via structured tool calls.

### 3. Artifact-Based Communication
- Agents write results to disk as **artifacts** (not passed as conversation context).
- Artifacts support **progressive disclosure** with multiple views: headline → summary_200 → summary_1000 → technical → full_report → raw_data.
- Parents receive only summaries + artifact IDs; they retrieve details only if needed.

### 4. Git-Like Provenance
- Every completed task creates a **Commit** with: task_id, agent_id, summary, artifact_ids, parent_ids, child_ids.
- Commits persist to disk, enabling reproducibility, branching, rollback, and caching.

### 5. Disposable Workers
- Agents do **not own memory** — state lives in artifacts and the commit repository.
- When an agent completes, its working context is discarded.

### 6. Runtime/Graph Separation
- The **Runtime** owns the task graph; agents never see it.
- The Runtime manages agent spawning, report delivery, budget requests, escalations, and failures.

---

## Key Components

| Component | File | Description |
|---|---|---|
| **Agent** | `core/agent.py` | Base agent class with tool-calling `run()` loop |
| **ToolRegistry** | `core/capabilities.py` | Defines all 10 tools with schemas and implementations |
| **Runtime** | `core/runtime.py` | Orchestrator: spawns agents, tracks graph, delivers results |
| **Task** | `core/task.py` | Task model (id, description, status, parent_id, metadata) |
| **ArtifactStore** | `artifact/store.py` | Persistent artifact storage with multi-view support |
| **Summary** | `artifact/summary.py` | Hierarchical summarization (headline → technical) |
| **Repository** | `memory/repository.py` | Git-like commit store with tree traversal |
| **LLMProvider** | `llm/provider.py` | Abstract interface for LLM backends |
| **OpenAIProvider** | `llm/openai_provider.py` | OpenAI/OpenRouter implementation |
| **CLI** | `cli/repl.py` | Interactive CLI with live Rich dashboard |

---

## Tests

Six test files covering:
- `test_agent.py` — Agent lifecycle and tool execution
- `test_artifact.py` — Artifact store CRUD and views
- `test_capabilities.py` — Tool registration and execution
- `test_repository.py` — Commit persistence and tree building
- `test_runtime.py` — Runtime orchestration, spawning, graph tracking

---

## Dependencies (from pyproject.toml)

- **pydantic >= 2.0** — Data modeling
- **openai >= 1.0** — LLM backend
- **python-dotenv >= 1.0** — Environment loading
- **pyyaml >= 6.0** — YAML support
- **httpx >= 0.27** — Async HTTP (webfetch)
- **rich >= 13.0** — CLI display
- **pytest >= 8.0, pytest-asyncio** (dev) — Testing

---

## Entry Points

- **CLI command**: `dynamic-harness [task description]` (via `cli/repl.py:main()`)
- **Programmatic**: Import `Runtime` from `dynamic_harness.core.runtime`, set up an LLM, spawn agents.

---

## Summary

This is a well-structured, novel agent framework that implements a sophisticated architectural vision — recursive agent decomposition, strict encapsulation, artifact-based communication, and Git-like provenance tracking. It's production-ready in its design and has comprehensive test coverage. The project is currently at version 0.1.0 and appears actively developed.
