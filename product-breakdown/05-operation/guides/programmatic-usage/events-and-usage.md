# Events & Usage

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

## Token Usage Tracking

```python
# Per-agent
usage = runtime.get_usage(agent.id)
print(f"Prompt: {usage['prompt_tokens']}, Completion: {usage['completion_tokens']}")

# Across all agents
total = runtime.total_usage()
print(f"Total tokens: {total['total_tokens']}")
```
