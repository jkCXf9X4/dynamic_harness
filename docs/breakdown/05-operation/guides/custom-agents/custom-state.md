---
id: INFO-097
type: info
title: Agent with Custom State
summary: Add per-agent state in __init__ and override _run_loop for custom behavior
date: 2026-09-23
status: current
---

# Agent with Custom State

```python
from collections import Counter

class TrackingAgent(Agent):
    def __init__(self, agent_id, task, runtime, parent=None):
        super().__init__(agent_id, task, runtime, parent)
        self.tool_calls_made = Counter()
        self.errors_hit = 0

    async def _run_loop(self) -> None:
        # Override core loop for custom behavior
        # Note: _run_loop is complex. For most cases, override run() instead.
        await super()._run_loop()
```

## Owns
- Adding per-agent state in __init__ and overriding _run_loop for custom behavior.

## Excludes
- Basic subclassing and registration: INFO-096
- Replacing the execution loop and pre/post hooks: INFO-099
- Choosing which override to use: INFO-101
