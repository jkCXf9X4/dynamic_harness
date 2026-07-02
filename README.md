# dynamic_harness

A recursive agent harness where agents dynamically spawn subagents depending on the task.

Based on the architectural principles from [starting_point.md](starting_point.md):

- **Agent hierarchy** (actor model) — agents know only parent, children, and task; no sibling/global visibility
- **Artifact-based communication** — agents produce disk artifacts + short summaries; raw context is never forwarded
- **Progressive disclosure** — each artifact has multiple views (headline → summary → full report)
- **Capability-based API** — agents have exactly `spawn()`, `report()`, `request_more_budget()`, `escalate()`, `fail()`
- **Disposable workers** — state lives in artifacts, not agent memory
- **Git-like provenance** — every completed task creates a commit with summary, artifact refs, parent/child links
- **Runtime/graph separation** — the runtime owns the task graph; agents never see it

## Structure

```
src/dynamic_harness/
├── core/
│   ├── agent.py           # Base Agent with capability API
│   ├── agent_examples.py  # ResearchAgent, PlannerAgent
│   ├── runtime.py         # Runtime (orchestrator, task graph, event handlers)
│   └── task.py            # Task, SpawnRequest, ReportPayload, etc.
├── artifact/
│   ├── store.py           # ArtifactStore with disk-backed progressive disclosure
│   └── summary.py         # Hierarchical summarization helpers
├── memory/
│   └── repository.py      # Git-like Repository (commits, tree, persistence)
└── llm/
    ├── provider.py        # Abstract LLMProvider
    └── openai_provider.py # OpenAI implementation
```

## Quick start

```python
import asyncio
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import Task
from dynamic_harness.core.agent_examples import PlannerAgent, ResearchAgent

runtime = Runtime(artifact_root=..., repo_root=...)

def factory(aid, task, runtime, parent):
    return PlannerAgent(aid, task, runtime, parent)

runtime.set_agent_factory(factory)

async def main():
    root = runtime.spawn_agent(Task(description="Analyze the repository"))
    await root.run()
    print(f"Spawned {runtime.agent_count()} agents")
    print(f"Commits: {runtime.repository.count()}")

asyncio.run(main())
```