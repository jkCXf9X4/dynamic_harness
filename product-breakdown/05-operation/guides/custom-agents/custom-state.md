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
