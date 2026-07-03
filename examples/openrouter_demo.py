from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv

from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import Task
from dynamic_harness.llm.openai_provider import OpenAIProvider

load_dotenv()


async def main() -> None:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("Set OPENROUTER_API_KEY environment variable")
        return

    tmp = Path(tempfile.mkdtemp())
    runtime = Runtime(
        artifact_root=tmp / "artifacts",
        repo_root=tmp / "repo",
        generated_root=tmp / "gen",
    )

    llm = OpenAIProvider(
        model="deepseek/deepseek-v4-flash",
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        verify_ssl=False,
    )
    runtime.set_llm(llm)

    runtime.on_report(lambda aid, p: print(f"\n[REPORT] {aid[:8]} | {p.summary[:200]}"))
    runtime.on_failure(lambda aid, f: print(f"\n[FAIL]  {aid[:8]} | {f.error}"))

    root = runtime.spawn_agent(Task(
        description="Create a Python agent that analyzes a git repository "
        "and produces a summary of the number of commits, contributors, "
        "and most changed files"
    ))

    print("=== Running MetaAgent with deepseek/deepseek-v4-flash ===\n")
    await root.run()

    print(f"\n=== Results ===")
    print(f"Agents spawned: {runtime.agent_count()}")
    print(f"Commits: {runtime.repository.count()}")
    print(f"Registered types: {list(runtime._agent_registry.keys())}")

    print(f"\nGenerated code (tmp/gen/):")
    for f in sorted(runtime.generated_root.glob("*.py")):
        if f.name == "__init__.py":
            continue
        print(f"\n--- {f.name} ---")
        print(f.read_text())

    print(f"\nTask graph:")
    for pid, kids in runtime.task_graph().items():
        print(f"  {pid[:8]} -> {[c[:8] for c in kids]}")


if __name__ == "__main__":
    asyncio.run(main())