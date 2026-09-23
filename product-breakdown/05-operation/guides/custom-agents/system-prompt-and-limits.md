# System Prompt & Safety Limits

## Custom System Prompt

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

## Custom Safety Limits

```python
class HighRiskAgent(Agent):
    def __init__(self, agent_id, task, runtime, parent=None):
        super().__init__(
            agent_id, task, runtime, parent,
            safety_max_iterations=200,   # Stricter safety
            repeated_call_limit=3,       # Faster stuck detection
        )
```
