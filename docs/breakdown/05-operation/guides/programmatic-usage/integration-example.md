---
id: INFO-126
type: info
title: Complete Integration Example
summary: End-to-end Python example wiring an OpenAI provider, a Runtime, and a delegated Task into one async analysis run with report collection and usage reporting.
date: 2026-09-23
status: current
---

# Complete Integration Example

```python
import asyncio
from pathlib import Path
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import Task
from dynamic_harness.llm.openai_provider import OpenAIProvider

async def run_analysis(repo_path: str) -> dict:
    """Run a complete codebase analysis."""
    provider = OpenAIProvider(
        api_key="...",
        model="deepseek/deepseek-v4-flash",
    )

    runtime = Runtime(
        artifact_root=Path("/tmp/analysis/artifacts"),
        repo_root=Path("/tmp/analysis/repo"),
    )
    runtime.set_llm(provider)

    results = []

    def collect(agent_id, payload):
        results.append({
            "agent_id": agent_id,
            "summary": payload.summary,
            "confidence": payload.confidence,
            "artifacts": payload.artifact_ids,
        })

    runtime.on_report(collect)

    agent = runtime.delegate(Task(
        description=f"Analyze {repo_path} for security vulnerabilities "
                     "and code quality issues. Write findings to disk."
    ))
    await agent.run()

    return {
        "status": agent.task.status.value,
        "agents_created": runtime.agent_count(),
        "total_tokens": runtime.total_usage()["total_tokens"],
        "results": results,
    }

asyncio.run(run_analysis("/path/to/repo"))
```

## Owns
- The complete end-to-end integration example: provider setup, Runtime construction, report collection, delegation, and result aggregation in one script.

## Excludes
- Artifact and repository layout: INFO-121
- Custom agent class definitions: INFO-122
- Delegation patterns: INFO-123
- No-LLM mode and error handling: INFO-124
- Event and usage APIs: INFO-125
- Runtime setup: INFO-127
