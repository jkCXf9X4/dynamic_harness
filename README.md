# dynamic_harness

A recursive agent harness where agents dynamically generate and spawn subagents **at runtime** — no fixed types.

Based on the architectural principles from [starting_point.md](starting_point.md):

- **Agent hierarchy** (actor model) — agents know only parent, children, and task; no sibling/global visibility
- **Artifact-based communication** — agents produce disk artifacts + short summaries; raw context is never forwarded
- **Progressive disclosure** — each artifact has multiple views (headline → summary → full report)
- **Capability-based API** — agents have exactly `spawn()`, `report()`, `request_more_budget()`, `escalate()`, `fail()`
- **Disposable workers** — state lives in artifacts, not agent memory
- **Git-like provenance** — every completed task creates a commit with summary, artifact refs, parent/child links
- **Runtime/graph separation** — the runtime owns the task graph; agents never see it

## How it works

There are **no pre-built agent types**. The only built-in agent is `MetaAgent`, which:

1. Takes a task description
2. Asks an LLM (or uses a fallback) to generate Python code for a specialist agent
3. Saves the code to `generated_root/` (in the tmp dir)
4. Dynamically loads and registers the new class
5. Spawns an instance of the new specialist
6. Reports the result

New specialist agents can themselves call `self.spawn()` to create deeper specialists — the `MetaAgent` is activated automatically whenever a task needs a new type.

```
User: "Analyze the repository for security issues"
       │
       ▼  Runtime spawns MetaAgent (default)
MetaAgent
       │
       ├── LLM generates SecurityAuditAgent.py
       ├── saves to disk, registers class
       ├── spawns SecurityAuditAgent
       │       │
       │       ├── spawn("audit auth module")
       │       │       └── MetaAgent → AuthAuditAgent → runs
       │       │
       │       └── report(summary) to MetaAgent
       │
       └── report(summary) to user
```

## Structure

```
src/dynamic_harness/
├── core/
│   ├── agent.py           # Agent base class + HARNESS_GUIDELINES
│   ├── meta_agent.py      # MetaAgent — generates new agent classes
│   ├── runtime.py         # Runtime (orchestrator, task graph, registry)
│   └── task.py            # Task, ReportPayload, Escalation, etc.
├── artifact/
│   ├── store.py           # ArtifactStore with progressive disclosure
│   └── summary.py         # Hierarchical summarization
├── memory/
│   └── repository.py      # Git-like Repository (commits, tree, persistence)
└── llm/
    ├── provider.py        # Abstract LLMProvider
    └── openai_provider.py # OpenAI implementation
```

## Agent guidelines

Every agent receives `HARNESS_GUIDELINES` (accessible via `self.guidelines`) that explain how to dynamically spawn subagents, what capabilities are available, and the encapsulation rules. The `MetaAgent` includes these guidelines in its code-generation prompt so generated agents know how to use the harness.

## Quick start

```python
import asyncio
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import Task

runtime = Runtime(artifact_root=..., repo_root=...)

async def main():
    root = runtime.spawn_agent(Task(description="Analyze the repository"))
    await root.run()
    print(f"Spawned {runtime.agent_count()} agents dynamically")

asyncio.run(main())
```

## Registering agent types

You can also register agent classes directly (useful for fixed entry points):

```python
runtime.register_agent_class("MyAgent", MyAgent)
root = runtime.spawn_agent(Task(description="..."), agent_type="MyAgent")
```