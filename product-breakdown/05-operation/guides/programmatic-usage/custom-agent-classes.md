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

See [custom agents](../custom-agents/README.md) for override points, custom
system prompts, and safety limits.
