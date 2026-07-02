from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from dynamic_harness.core.agent import Agent
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import ReportPayload, Task


async def main() -> None:
    tmp = Path(tempfile.mkdtemp())
    runtime = Runtime(artifact_root=tmp / "artifacts", repo_root=tmp / "repo", generated_root=tmp / "gen")

    runtime.on_report(lambda aid, p: print(f"[REPORT] {aid[:8]} | {p.summary[:80]}..."))
    runtime.on_failure(lambda aid, f: print(f"[FAIL]  {aid[:8]} | {f.error}"))

    # Register a few specialist types up front for the demo
    class ResearcherAgent(Agent):
        async def run(self) -> None:
            result = f"Researched: {self.task.description}"
            self.report(ReportPayload(
                task_id=self.task.id,
                summary=result,
            ))

    class ReviewerAgent(Agent):
        async def run(self) -> None:
            result = f"Reviewed: {self.task.description}"
            self.report(ReportPayload(
                task_id=self.task.id,
                summary=result,
            ))

    runtime.register_agent_class("ResearcherAgent", ResearcherAgent)
    runtime.register_agent_class("ReviewerAgent", ReviewerAgent)

    # A decomposing agent that spawns specialists
    class DecomposerAgent(Agent):
        async def run(self) -> None:
            subtasks = [
                "Research authentication patterns",
                "Review existing security measures",
            ]
            children = [
                self.spawn(subtasks[0], agent_type="ResearcherAgent"),
                self.spawn(subtasks[1], agent_type="ReviewerAgent"),
            ]
            for c in children:
                await c.run()
            self.report(ReportPayload(
                task_id=self.task.id,
                summary="Decomposition complete",
                next_actions=[],
            ))

    runtime.register_agent_class("DecomposerAgent", DecomposerAgent)

    # Also demonstrate the MetaAgent: dynamically generate a new specialist
    print("--- Phase 1: spawning MetaAgent that generates a SecurityAuditAgent ---")
    meta = runtime.spawn_agent(Task(
        description="Create a SecurityAuditAgent that scans for vulnerabilities"
    ))
    await meta.run()

    print(f"\nRegistered types after MetaAgent: {list(runtime._agent_registry.keys())}")

    # Now use the fixed decomposition
    print("\n--- Phase 2: using registered DecomposerAgent ---")
    root = runtime.spawn_agent(Task(description="Security review"), agent_type="DecomposerAgent")
    await root.run()

    print(f"\nTotal agents: {runtime.agent_count()}")
    print(f"Commits: {runtime.repository.count()}")

    print("\nTask graph:")
    for pid, kids in runtime.task_graph().items():
        print(f"  {pid[:8]} -> {[c[:8] for c in kids]}")


if __name__ == "__main__":
    asyncio.run(main())