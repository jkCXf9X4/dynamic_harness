from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from dynamic_harness.core.agent_examples import PlannerAgent, ResearchAgent
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import Task


def make_agent(agent_id: str, task: Task, runtime: Runtime, parent: object = None) -> object:
    from dynamic_harness.core.agent import Agent
    parent_agent = parent if isinstance(parent, Agent) else None
    if "planner" in task.description.lower() or parent is None:
        return PlannerAgent(agent_id, task, runtime, parent_agent)
    return ResearchAgent(agent_id, task, runtime, parent_agent)


async def main() -> None:
    tmp = Path(tempfile.mkdtemp())
    runtime = Runtime(artifact_root=tmp / "artifacts", repo_root=tmp / "repo")
    runtime.set_agent_factory(make_agent)

    root_task = Task(description="Analyze the repository structure and produce a security report")
    root = runtime.spawn_agent(root_task)

    runtime.on_report(lambda aid, payload: print(f"\n[REPORT] Agent {aid[:8]} completed"))
    runtime.on_failure(lambda aid, fail: print(f"\n[FAIL] Agent {aid[:8]}: {fail.error}"))

    await root.run()

    print(f"\nTotal agents spawned: {runtime.agent_count()}")
    print(f"Total commits: {runtime.repository.count()}")

    print("\nTask graph:")
    for parent_id, children in runtime.task_graph().items():
        print(f"  {parent_id[:8]} -> {[c[:8] for c in children]}")

    print("\nRecent commits:")
    for c in runtime.repository.log(limit=5):
        print(f"  {c.id[:8]} | {c.summary[:80]}...")


if __name__ == "__main__":
    asyncio.run(main())