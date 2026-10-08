---
id: INFO-122
type: info
title: Custom Agent Classes
summary: `python from dynamic_harness.core.agent import Agent
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
