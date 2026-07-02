from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import Task


async def main() -> None:
    tmp = Path(tempfile.mkdtemp())
    runtime = Runtime(artifact_root=tmp / "artifacts", repo_root=tmp / "repo", generated_root=tmp / "gen")

    runtime.on_report(lambda aid, p: print(f"[REPORT] {aid[:8]} | {p.summary[:100]}..."))
    runtime.on_failure(lambda aid, f: print(f"[FAIL]  {aid[:8]} | {f.error}"))

    root = runtime.spawn_agent(Task(
        description="Analyze the repository structure and produce a security report"
    ))
    await root.run()

    print(f"\nAgents spawned: {runtime.agent_count()}")
    print(f"Commits: {runtime.repository.count()}")

    print("\nTask graph:")
    for pid, kids in runtime.task_graph().items():
        print(f"  {pid[:8]} -> {[c[:8] for c in kids]}")

    print(f"\nRegistered types: {list(runtime._agent_registry.keys())}")


if __name__ == "__main__":
    asyncio.run(main())