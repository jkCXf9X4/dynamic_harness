# dynamic_harness

A recursive agent harness with **tool-calling agents** — agents interact with the environment via structured tool calls, not generated code.

Based on the architectural principles from [starting_point.md](starting_point.md):

- **Agent hierarchy** (actor model) — agents know only parent, children, and task; no sibling/global visibility
- **Artifact-based communication** — agents produce disk artifacts + short summaries; raw context is never forwarded
- **Progressive disclosure** — each artifact has multiple views (headline → summary → full report)
- **Tool-calling loop** — agents read, write, glob, webfetch, edit, spawn subagents, report, escalate, and fail via structured tool calls
- **Spawning = decomposition** — `spawn()` creates a sub-agent that runs the same tool loop with a focused task
- **Disposable workers** — state lives in artifacts, not agent memory
- **Git-like provenance** — every completed task creates a commit with summary, artifact refs, parent/child links
- **Runtime/graph separation** — the runtime owns the task graph; agents never see it

## How it works

There is **one agent loop** that every agent uses:

1. Receive a task description + a set of available tools (read, write, glob, webfetch, edit, spawn, report, escalate, fail)
2. The LLM decides whether to call a tool or return a final answer
3. Tool results are fed back into the conversation
4. When the agent calls `report()`, its work is committed and the result flows to the parent

Sub-agents are created via the `spawn()` tool — they get their own fresh conversation and a focused subtask. There is **no code generation**, no dynamic imports, no generated files.

```
User: "Analyze /home/eriro/pwa for security issues"
       │
       ▼  Runtime spawns Agent (with LLM)
   Agent
       │  LLM decides:
       ├── glob("**/*.py") → [file list]
       ├── read("src/auth.py") → content
       ├── spawn("Audit auth module") → sub-agent result
       │       └── sub-agent runs same loop (glob + read + report)
       └── report(Summary) to parent
```

## Structure

```
src/dynamic_harness/
├── core/
│   ├── agent.py           # Agent base class + tool-calling run() loop
│   ├── meta_agent.py      # MetaAgent subclass (specialized system prompt)
│   ├── capabilities.py    # ToolDef, ToolCall, ToolRegistry, tool impls
│   ├── runtime.py         # Runtime (orchestrator, task graph, tool registry)
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

## Available tools

| Tool | Description |
|---|---|
| `read(path)` | Read a file from disk |
| `write(path, content)` | Write content to a file |
| `glob(pattern)` | List files matching a glob pattern |
| `webfetch(url)` | Fetch content from a URL |
| `edit(path, old_string, new_string)` | Find and replace text in a file |
| `spawn(description)` | Create a sub-agent to handle a subtask |
| `report(summary, artifact_ids)` | Report final results (completes the agent) |
| `escalate(issue)` | Escalate to parent agent |
| `fail(error)` | Report a failure |

## Quick start

```python
import asyncio
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import Task
from dynamic_harness.llm.openai_provider import OpenAIProvider

runtime = Runtime(artifact_root=..., repo_root=...)
runtime.set_llm(OpenAIProvider(model="gpt-4o"))

async def main():
    root = runtime.spawn_agent(Task(description="Find the 3 largest .py files"))
    await root.run()
    print(f"Spawned {runtime.agent_count()} agents")

asyncio.run(main())
```

## Without an LLM

If no LLM is set, the agent immediately reports the task description as its summary — useful for testing and non-AI workflows.

## Registering agent types

You can register custom agent classes for reusable entry points:

```python
class MyAgent(Agent):
    async def run(self) -> None:
        # override or use super().run() for the tool loop
        ...

runtime.register_agent_class("MyAgent", MyAgent)
root = runtime.spawn_agent(Task(description="..."), agent_type="MyAgent")
```
