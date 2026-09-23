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
