# Usage & Responsibilities

## Token Usage Tracking

The Runtime records per-agent consumption after each LLM response:

```python
runtime.record_usage(
    agent_id,
    prompt_tokens=response.usage.prompt_tokens,
    completion_tokens=response.usage.completion_tokens,
    message_count=len(messages),
)

usage = runtime.get_usage(agent.id)
# {"prompt_tokens": 15000, "completion_tokens": 3000, "total_tokens": 18000, "message_count": 25}
```

## Agent vs Runtime Responsibilities

| Concern | Agent | Runtime |
|---------|-------|---------|
| Tool calling loop | ✓ | — |
| Tool execution | — | ✓ (ToolRegistry) |
| Task status management | — | ✓ |
| Artifact creation | — | ✓ |
| Commit creation | — | ✓ |
| Event dispatching | — | ✓ |
| Token tracking | — | ✓ |
| Delegation (creating children) | ✓ | ✓ (registration) |
| Safety limits | ✓ | — |
| Context management | ✓ | — |

Agents are self-contained execution units; the Runtime is shared infrastructure.
This separation enables the actor-model design — agents share nothing except via
the Runtime's controlled interfaces.
