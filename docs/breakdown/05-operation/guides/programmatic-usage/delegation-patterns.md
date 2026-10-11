---
id: INFO-123
type: info
title: Delegation Patterns
summary: Patterns for delegating tasks programmatically: sequential chaining, parallel execution, and task graph inspection.
date: 2026-09-23
status: current
---

# Delegation Patterns

## Sequential Tasks

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

## Parallel Agents

```python
agent_a = runtime.delegate(Task(description="Search for bugs in src/core/"))
agent_b = runtime.delegate(Task(description="Search for bugs in src/cli/"))

await asyncio.gather(agent_a.run(), agent_b.run())

print(f"A: {agent_a.task.status.value}")
print(f"B: {agent_b.task.status.value}")
```

## Task Graph Inspection

```python
graph = runtime.task_graph()
# {"abc123": ["def456", "ghi789"], "def456": [], "ghi789": []}

for parent_id, child_ids in graph.items():
    agent = runtime.get_agent(parent_id)
    children = ", ".join(child_ids)
    print(f"  {parent_id[:8]} ({agent.task.status.value}) → [{children}]")
```

## Owns
- Delegation patterns: sequential task chaining, parallel agent execution, and task graph inspection.

## Excludes
- Runtime construction and configuration: INFO-127
- Custom agent classes: INFO-122
- Artifact and repository access: INFO-121
- No-LLM mode and error handling: INFO-124
- Events and usage tracking: INFO-125
- Complete integration example: INFO-126
