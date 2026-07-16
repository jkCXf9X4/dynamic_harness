---
title: "Programmatic Usage"
category: guide
difficulty: intermediate
summary: >
  How to embed Dynamic Harness as a library. Covers constructing a Runtime,
  delegating tasks, handling events, token tracking, and integration patterns.
related:
  - api/runtime.md
  - api/agent.md
  - api/task.md
  - api/llm.md
---

# Programmatic Usage

Dynamic Harness can be embedded as a Python library — no CLI required. This is useful for integrating agent workflows into existing applications, building custom orchestrators, or running automated pipelines.

## Minimal Example

```python
import asyncio
from pathlib import Path
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import Task
from dynamic_harness.llm.openai_provider import OpenAIProvider

async def main():
    provider = OpenAIProvider(api_key="sk-...")
    runtime = Runtime(
        artifact_root=Path("/tmp/artifacts"),
        repo_root=Path("/tmp/repo"),
    )
    runtime.set_llm(provider)

    agent = runtime.delegate(Task(description="Count .py files in src/"))
    await agent.run()

    print(f"Status: {agent.task.status.value}")
    print(f"Last report: {agent._last_report.summary if agent._last_report else 'None'}")

asyncio.run(main())
```

## Runtime Setup

The Runtime needs at minimum `artifact_root` and `repo_root`. Optional arguments:

```python
from tempfile import mkdtemp

runtime = Runtime(
    artifact_root=Path("/path/to/artifacts"),
    repo_root=Path("/path/to/repo"),
    trace_root=Path("/path/to/traces"),      # JSONL debug traces
    generated_root=Path("/path/to/output"),  # Generated file output
)
```

For temporary, non-persistent use:

```python
runtime = Runtime(
    artifact_root=Path(mkdtemp()),
    repo_root=Path(mkdtemp()),
)
```

## Event Handlers

Register callbacks for agent lifecycle events:

```python
def on_report_callback(agent_id: str, payload: ReportPayload):
    print(f"[{agent_id[:8]}] Completed: {payload.summary[:80]}")
    if payload.confidence and payload.confidence < 0.5:
        print(f"  WARNING: Low confidence ({payload.confidence})")

def on_failure_callback(agent_id: str, failure: Failure):
    print(f"[{agent_id[:8]}] FAILED: {failure.error}")

runtime.on_report(on_report_callback)
runtime.on_failure(on_failure_callback)
```

All handlers receive `(agent_id: str, payload)`:
- `on_report(agent_id, ReportPayload)`
- `on_escalation(agent_id, Escalation)`
- `on_failure(agent_id, Failure)`
- `on_budget_request(agent_id, BudgetRequest)`

## Delegation Patterns

### Sequential Tasks

```python
# Run a task, then use its result
agent1 = runtime.delegate(Task(description="Analyze auth.py"))
await agent1.run()
print(f"First task: {agent1._last_report.summary}")

# Run a follow-up using the first task's output
agent2 = runtime.delegate(Task(
    description="Based on the analysis, fix the issues found",
    metadata={"previous_report": agent1._last_report.summary},
))
await agent2.run()
```

### Parallel Agents

```python
agent_a = runtime.delegate(Task(description="Search for bugs in src/core/"))
agent_b = runtime.delegate(Task(description="Search for bugs in src/cli/"))

await asyncio.gather(agent_a.run(), agent_b.run())

print(f"A: {agent_a.task.status.value}")
print(f"B: {agent_b.task.status.value}")
```

### Task Graph Inspection

```python
graph = runtime.task_graph()
# {"abc123": ["def456", "ghi789"], "def456": [], "ghi789": []}

for parent_id, child_ids in graph.items():
    agent = runtime.get_agent(parent_id)
    children = ", ".join(child_ids)
    print(f"  {parent_id[:8]} ({agent.task.status.value}) → [{children}]")
```

## Token Usage Tracking

```python
# Per-agent
usage = runtime.get_usage(agent.id)
print(f"Prompt: {usage['prompt_tokens']}, Completion: {usage['completion_tokens']}")

# Across all agents
total = runtime.total_usage()
print(f"Total tokens: {total['total_tokens']}")
```

## Working with Artifacts

```python
# After a task completes, read its artifacts
artifact = runtime.artifact_store.get(artifact_id)
if artifact:
    print(f"Headline: {artifact.views.headline}")
    print(f"Summary:  {artifact.views.summary_200}")

# Read files written by agents
content = runtime.artifact_store.read_text(artifact_id, "findings.json")
```

## Working with the Repository

```python
# View commit history
commits = runtime.repository.log(limit=20)
for c in commits:
    print(f"{c.id[:8]} [{c.timestamp:%H:%M}] {c.summary[:60]}")

# View commit tree
tree = runtime.repository.tree()
```

## Custom Agent Classes

```python
from dynamic_harness.core.agent import Agent

class LoggingAgent(Agent):
    async def run(self):
        print(f"[{self.id[:8]}] Starting: {self.task.description}")
        await super().run()
        print(f"[{self.id[:8]}] Done: {self.task.status.value}")

runtime.register_agent_class("logging", LoggingAgent)

agent = runtime.delegate(
    Task(description="Do a thing"),
    agent_type="logging",
)
await agent.run()
```

## Session Management

```python
# Reset for a clean session
runtime.reset()

# All state cleared: agents, task graph, usage, events, artifacts, commits
```

## Complete Integration Example

```python
import asyncio
from pathlib import Path
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import Task
from dynamic_harness.llm.openai_provider import OpenAIProvider

async def run_analysis(repo_path: str) -> dict:
    """Run a complete codebase analysis."""
    provider = OpenAIProvider(
        api_key="...",
        model="deepseek/deepseek-v4-flash",
    )

    runtime = Runtime(
        artifact_root=Path("/tmp/analysis/artifacts"),
        repo_root=Path("/tmp/analysis/repo"),
    )
    runtime.set_llm(provider)

    results = []

    def collect(agent_id, payload):
        results.append({
            "agent_id": agent_id,
            "summary": payload.summary,
            "confidence": payload.confidence,
            "artifacts": payload.artifact_ids,
        })

    runtime.on_report(collect)

    agent = runtime.delegate(Task(
        description=f"Analyze {repo_path} for security vulnerabilities "
                     "and code quality issues. Write findings to disk."
    ))
    await agent.run()

    return {
        "status": agent.task.status.value,
        "agents_created": runtime.agent_count(),
        "total_tokens": runtime.total_usage()["total_tokens"],
        "results": results,
    }

asyncio.run(run_analysis("/path/to/repo"))
```

## No-LLM Mode

For testing or LLM-free workflows, skip `runtime.set_llm()`:

```python
runtime = Runtime(artifact_root=..., repo_root=...)
# No set_llm() call

agent = runtime.delegate(Task(description="Write a report"))
await agent.run()
# agent._last_report.summary == "Agent abc123 executed: Write a report"
```

## Error Handling

```python
agent = runtime.delegate(Task(description="Risky operation"))
await agent.run()

if agent.task.status == TaskStatus.failed:
    print(f"Failed: {agent._last_failure.error}")
    print(f"Trace: {agent._last_failure.trace}")

elif agent.task.status == TaskStatus.escalated:
    print(f"Escalated — needs parent intervention")
```