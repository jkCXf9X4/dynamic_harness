---
id: INFO-127
type: info
title: Runtime Setup
summary: Programmatic Runtime setup: minimal example, constructor arguments, and session reset
date: 2026-09-23
status: current
---

# Runtime Setup

## Minimal Example

```python
import asyncio
from pathlib import Path
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import Task
from dynamic_harness.llm.openai_provider import OpenAIProvider

async def main():
    provider = OpenAIProvider(api_key="sk-...")
    runtime = Runtime(
        artifact_root=Path("/tmp/artifacts"),
        repo_root=Path("/tmp/repo"),
    )
    runtime.set_llm(provider)

    agent = runtime.delegate(Task(description="Count .py files in src/"))
    await agent.run()

    print(f"Status: {agent.task.status.value}")
    print(f"Last report: {agent._last_report.summary if agent._last_report else 'None'}")

asyncio.run(main())
```

## Runtime Arguments

The Runtime needs at minimum `artifact_root` and `repo_root`. Optional arguments:

```python
from tempfile import mkdtemp

runtime = Runtime(
    artifact_root=Path("/path/to/artifacts"),
    repo_root=Path("/path/to/repo"),
    trace_root=Path("/path/to/traces"),      # JSONL debug traces
    generated_root=Path("/path/to/output"),  # Generated file output
)
```

For temporary, non-persistent use:

```python
runtime = Runtime(
    artifact_root=Path(mkdtemp()),
    repo_root=Path(mkdtemp()),
)
```

## Session Management

```python
# Reset for a clean session
runtime.reset()

# Cleared: agents, task graph, usage, artifacts, commits, traces
# (event handlers are only cleared with runtime.reset(clear_handlers=True))
```

## Owns
- Runtime construction: required and optional constructor arguments, including temporary non-persistent roots.
- Session lifecycle: what `runtime.reset()` clears and how to keep event handlers.

## Excludes
- Artifact and repository access after setup: INFO-121
- Custom agent classes: INFO-122
- Delegation patterns: INFO-123
- No-LLM mode and error handling: INFO-124
- Events and usage tracking: INFO-125
- End-to-end integration: INFO-126
