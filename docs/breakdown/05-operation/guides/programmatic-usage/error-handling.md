---
id: INFO-124
type: info
title: No-LLM Mode & Error Handling
summary: No-LLM mode behavior and how to inspect failed or escalated task results
date: 2026-09-23
status: current
---

# No-LLM Mode & Error Handling

## No-LLM Mode

If you skip `runtime.set_llm()`, agents enter no-LLM mode:

```python
runtime = Runtime(artifact_root=..., repo_root=...)
# No set_llm() call

agent = runtime.delegate(Task(description="Write a report"))
await agent.run()
# agent.task.status == TaskStatus.failed
# agent._last_failure.error == "No LLM provider configured"
```

- No-LLM mode produces no report.
- The agent fails immediately with `"No LLM provider configured"`.
- Use it to verify tool and runtime infrastructure, not to produce output.

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

## Owns

- No-LLM mode behavior when no LLM provider is configured
- Inspecting failed or escalated task results via `agent.task.status` and `agent._last_failure`

## Excludes

- Runtime construction and LLM provider setup: INFO-127
- Delegation patterns and task decomposition: INFO-123
- Event handling and usage tracking: INFO-125
- End-to-end integration: INFO-126
