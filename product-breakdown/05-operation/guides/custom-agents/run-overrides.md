# Run Overrides

## Complete Run Override

Replace the entire execution loop:

```python
class PreprocessingAgent(Agent):
    async def run(self) -> None:
        llm = self.llm
        if not llm:
            # No-LLM fallback
            self.report(ReportPayload(
                task_id=self.task.id,
                summary=f"Preprocessed: {self.task.description}",
            ))
            return

        # Do custom work before the tool loop
        pre_result = await llm.generate(
            system="You are a preprocessor. Summarize the task into a structured plan.",
            user=self.task.description,
        )

        # Modify the task description
        self.task.description = pre_result.content
        await super().run()
```

## Pre/Post Hooks

Override `run()` to add behavior around the standard loop:

```python
class AuditingAgent(Agent):
    async def run(self) -> None:
        start = datetime.now(timezone.utc)
        await super().run()
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()

        usage = self._runtime.get_usage(self.id)
        print(f"[AUDIT] {self.id[:8]} completed in {elapsed:.1f}s")
        print(f"[AUDIT] Tokens: {usage['total_tokens']}")
```
