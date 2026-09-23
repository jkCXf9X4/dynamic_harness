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

No-LLM mode does **not** produce a report — the agent fails immediately with
`"No LLM provider configured"`. It is only useful for verifying tool/runtime
infrastructure, not for producing output.

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
