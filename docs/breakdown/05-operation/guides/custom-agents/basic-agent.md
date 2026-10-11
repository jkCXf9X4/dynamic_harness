---
id: INFO-096
type: info
title: Basic Custom Agent
summary: Subclass Agent, override run(), register the class, and delegate by name
date: 2026-09-23
status: current
---

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

## Owns
- The minimal custom agent pattern: subclass Agent, override run(), register the class, delegate by name.

## Excludes
- Per-agent state and _run_loop overrides: INFO-097
- Replacing the execution loop and pre/post hooks: INFO-099
- Choosing which override to use: INFO-101
