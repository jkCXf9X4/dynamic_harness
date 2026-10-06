---
title: "Dynamic Harness — AI Agent Onboarding"
category: meta
summary: >
  Structured reference for AI coding agents. Project overview, architecture
  principles, key files, conventions, and extension points. Read this first
  before making any changes.
model_refs:
  - Task, TaskStatus, ReportPayload, Escalation, Failure, BudgetRequest, AgentOutcome
  - Agent, Runtime, ToolRegistry, ToolDef, ToolResult, ToolContext
  - Skill, SkillRegistry
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


# Context Budget — Prefer Subagents

- Use subagents as much as possible: the current model has a limited context, and heavy reading (file exploration, long documents, search sweeps) fills it fast.
- Delegate broad, self-contained information gathering to subagents (`explore` for codebase/search questions, `general` for multi-step research or parallel work), and consume only their summaries.
- Run independent tasks in parallel subagents; keep the main session for decisions, edits, and synthesis.
- Write large artifacts directly to files rather than streaming them through the conversation.


# Git guidelines

Do not commit after changes. Enable manual review before commits


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
├── __main__.py          → entry: python -m dynamic_harness
├── config.py            → HarnessConfig, LLMProviderConfig, SafetyConfig, harness.json loading
├── api/harness.py       → Harness (high-level programmatic API)
├── core/
│   ├── agent.py         → Agent class + system prompt + run() loop + safety
│   ├── runtime.py       → Runtime orchestrator (task graph, events, run())
│   ├── task.py          → Task, ReportPayload, Escalation, Failure, AgentOutcome
│   ├── context.py       → AgentContext (turns, prune/restore/compress)
│   ├── references.py    → skills root resolution + SkillRegistry
│   ├── policies/        → composable host-agnostic decision objects (SpawnPolicy, LoopGuard, …)
│   ├── comms/           → swappable communication backends (relay/siblings/shared/topics)
│   ├── tools/           → ToolRegistry + tools split by concern (filesystem, process, network, agents, …)
│   └── …                → support modules (events, usage, trace, telemetry, checkpoint, environment, prompts, tool_context)
├── cli/                 → terminal CLI, tree/stats rendering, state persistence
├── artifact/            → ArtifactStore (progressive disclosure) + summaries
├── memory/              → Repository (Git-like provenance commits)
├── benchmark/           → deterministic task suite + scoring + standalone CLI
└── llm/                 → LLMProvider ABC + OpenAIProvider

tests/                   → pytest suite (backend/ + cli/)
product-breakdown/       → systems-engineering record (seven layers; start at its README.md)
docs/                    → api/ (module-level API reference) + references/ (rationale library)
.agents/skills/          → installed skills (gitignored; source: 3rd_party/agent_methods_and_tools)
```

## Where the Detail Lives

This file is onboarding only. Canonical detail lives in `docs/api/` — one page
per module. **Do not restate it here**; read the page instead.

| Topic | Read |
|-------|------|
| Agent loop, safety invariants, checkpoints | `docs/api/agent.md` |
| Runtime lifecycle, events, resume | `docs/api/runtime.md` |
| Task / ReportPayload models | `docs/api/task.md` |
| All 34 tools (parameters, terminal tools, result caching) | `docs/api/tools.md` |
| Every harness.json setting (0/null = cap off) | `docs/api/config.md` |
| Policies layer | `docs/api/policies.md` |
| Artifacts, commits, LLM providers | `docs/api/artifacts.md`, `docs/api/repository.md`, `docs/api/llm.md` |

Data flow, in one line: `User/CLI → Runtime.delegate(Task) → Agent.run()` (tool-calling loop; recursive delegation) `→ report() → Runtime.deliver_report() → ArtifactStore.save() + Repository.commit()`.

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
| Custom timing/policy decision | Construct a `core/policies/` object (e.g. `SpawnPolicy`, `RetryPolicy`) and pass it into `Runtime`/`ToolRegistry`, or subclass it |
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
| Change agent methodology | `product-breakdown/02-architecture/methodology/README.md` |
| Change rationale / reference library | `core/references.py` + `docs/references/` + installed skills (`3rd_party/agent_methods_and_tools/methods/` → `.agents/skills/`) |



### Information Hygiene — Mandatory

* **Maintain canonical state, not historical accumulation.** Whenever information changes, **remove, replace, or supersede stale information**. Do not simply append new information on top of existing information.

* **Treat excessive information as an anti-pattern.** Unnecessary, redundant, outdated, or conflicting information increases cognitive load, slows development, and creates ambiguity. **Prefer the smallest set of information necessary to represent the current canonical state.**

* **Determine the canonical disposition before storing information.** For every piece of information, evaluate whether it should be **created, updated, replaced, merged, superseded, or removed**.

* **Prevent duplication and contradiction.** Before adding information, check whether an existing representation already covers it. Update the existing source of truth rather than creating another competing representation.

* **Do not preserve stale state by default.** Historical information should only be retained when it has an explicit purpose and a clearly defined place to live.

* **Optimize for future retrieval and action.** Information should be structured so an agent can quickly determine **what is current, what is authoritative, and what should be ignored**.
