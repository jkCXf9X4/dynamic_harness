# Basic Custom Agent

```python
from dynamic_harness.core.agent import Agent

class MyAgent(Agent):
    async def run(self) -> None:
        print(f"[{self.id[:8]}] Starting task: {self.task.description}")
        await super().run()
        print(f"[{self.id[:8]}] Completed: {self.task.status.value}")
```

## Registration

```python
runtime.register_agent_class("my_agent", MyAgent)
```

## Usage via delegate

```python
# Via the delegate() tool in the LLM loop:
#   delegate(description="...", agent_type="my_agent")
# Only registered names are accepted; an unknown agent_type is rejected with an
# error rather than silently falling back to the base Agent.

# Or programmatically:
agent = runtime.delegate(task, agent_type="my_agent")
await agent.run()
```
