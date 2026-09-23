# Full Example: Retry Agent

An agent that automatically retries on failure up to N times:

```python
from dynamic_harness.core.task import TaskStatus

class RetryAgent(Agent):
    def __init__(self, agent_id, task, runtime, parent=None, max_retries=3):
        super().__init__(agent_id, task, runtime, parent)
        self.max_retries = max_retries

    async def run(self) -> None:
        for attempt in range(1, self.max_retries + 1):
            self.task.status = TaskStatus.pending  # Reset
            await super().run()

            if self.task.status == TaskStatus.completed:
                return

            print(f"[RETRY] Attempt {attempt} failed, retrying...")
            # Clear messages for fresh context on retry
            self._messages = None
            self._iteration = 0
            self._recent_batches = None

        print(f"[RETRY] All {self.max_retries} attempts failed")
```
