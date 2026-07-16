---
title: "Custom Agents"
category: guide
difficulty: advanced
summary: >
  How to create custom Agent subclasses — overriding the run loop, adding
  hooks, injecting custom system prompts, and registering named agent types
  for programmatic delegation.
related:
  - api/agent.md
  - api/runtime.md
  - guides/programmatic-usage.md
---

# Custom Agents

Agent behavior can be customized by subclassing `Agent` and overriding key methods. Custom agents are registered with the Runtime and referenced by name during delegation.

## Basic Custom Agent

```python
from dynamic_harness.core.agent import Agent

class MyAgent(Agent):
    async def run(self) -> None:
        print(f"[{self.id[:8]}] Starting task: {self.task.description}")
        await super().run()
        print(f"[{self.id[:8]}] Completed: {self.task.status.value}")
```

### Registration

```python
runtime.register_agent_class("my_agent", MyAgent)
```

### Usage via delegate

```python
# Via the delegate() tool in the LLM loop:
#   delegate(description="...", agent_type="my_agent")

# Or programmatically:
agent = runtime.delegate(task, agent_type="my_agent")
await agent.run()
```

## Override Points

### Complete Run Override

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

### Pre/Post Hooks

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

### Custom System Prompt

Pass a custom system prompt when constructing:

```python
class SecurityAgent(Agent):
    def __init__(self, agent_id, task, runtime, parent=None):
        custom_prompt = f"""{AGENT_SYSTEM_PROMPT}

You are a specialized security agent. Your ONLY concern is security
vulnerabilities. Ignore style, performance, architecture. Flag issues,
do not fix them. For each finding, assign a CVSS score.
"""
        super().__init__(agent_id, task, runtime, parent, system_prompt=custom_prompt)
```

Or pass via the `Task`:

```python
task = Task(
    description="Audit the codebase",
    role="Security Auditor",
    system_prompt=my_custom_prompt,
)
agent = runtime.delegate(task, agent_type="my_agent")
```

### Custom Safety Limits

```python
class HighRiskAgent(Agent):
    def __init__(self, agent_id, task, runtime, parent=None):
        super().__init__(
            agent_id, task, runtime, parent,
            safety_max_iterations=200,   # Stricter safety
            repeated_call_limit=3,       # Faster stuck detection
        )
```

## Agent with Custom State

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

## Full Example: Retry Agent

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

## When to Use Custom Agents

| Use case | Approach |
|----------|----------|
| Logging/metrics | Override `run()` with pre/post hooks |
| Task preprocessing | Override `run()`, modify task, call `super().run()` |
| Domain specialization | Custom system prompt |
| Different safety thresholds | Override `safety_max_iterations` |
| Retry logic | Custom `run()` with loop around `super().run()` |

Custom agent classes let you encode reusable behavior patterns without modifying the core `Agent` implementation.