---
id: INFO-122
type: info
title: Custom Agent Classes
summary: How to subclass Agent, register a named agent class with the runtime, and delegate tasks to it by name.
date: 2026-09-23
status: current
---

# Custom Agent Classes

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

See custom agents (`custom-agents`) for override points, custom
system prompts, and safety limits.

## Owns

- Subclassing Agent for programmatic use, including overriding the run loop
- Registering a named agent class with the runtime via register_agent_class
- Delegating a task to a custom agent class by name via agent_type

## Excludes

- Delegation patterns such as sequential and parallel tasks: INFO-123
- Runtime construction and configuration: INFO-127
- Event handling and token usage tracking: INFO-125
- No-LLM mode and error handling: INFO-124
- Reading artifacts and repository history: INFO-121
- End-to-end integration example: INFO-126
