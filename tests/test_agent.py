from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from dynamic_harness.core.agent import Agent
from dynamic_harness.core.agent_examples import ResearchAgent
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import ReportPayload, Task


class TrackingResearchAgent(ResearchAgent):
    def __init__(self, agent_id: str, task: Task, runtime: Runtime, parent: Agent | None = None) -> None:
        super().__init__(agent_id, task, runtime, parent)
        self.log: list[str] = []

    async def _execute(self) -> ReportPayload:
        self.log.append(f"execute: {self.task.description}")
        return ReportPayload(
            task_id=self.task.id,
            summary=f"Result: {self.task.description}",
            claims=[f"Claim about {self.task.description[:50]}"],
            next_actions=[],
        )


@pytest.fixture
def runtime() -> Runtime:
    tmp = Path(tempfile.mkdtemp())
    return Runtime(artifact_root=tmp / "artifacts", repo_root=tmp / "repo")


@pytest.mark.asyncio
async def test_agent_spawn_and_report(runtime: Runtime) -> None:
    runtime.set_agent_factory(TrackingResearchAgent)

    root_task = Task(description="Analyze the repository")
    root = runtime.spawn_agent(root_task)
    await root.run()

    assert root.task.status.value == "completed"
    assert runtime.agent_count() == 1


@pytest.mark.asyncio
async def test_agent_hierarchy(runtime: Runtime) -> None:
    runtime.set_agent_factory(TrackingResearchAgent)

    root_task = Task(description="Research project")
    root = runtime.spawn_agent(root_task)

    child1 = root.spawn("Security audit")
    child2 = root.spawn("Architecture review")

    await child1.run()
    await child2.run()

    assert child1.task.status.value == "completed"
    assert child2.task.status.value == "completed"

    graph = runtime.task_graph()
    assert root.id in graph
    assert child1.id in graph[root.id]
    assert child2.id in graph[root.id]


@pytest.mark.asyncio
async def test_agent_failure(runtime: Runtime) -> None:
    class FailingAgent(TrackingResearchAgent):
        async def _execute(self) -> ReportPayload:
            raise RuntimeError("Something went wrong")

    runtime.set_agent_factory(FailingAgent)

    root_task = Task(description="Failing task")
    root = runtime.spawn_agent(root_task)
    await root.run()

    assert root.task.status.value == "failed"


@pytest.mark.asyncio
async def test_agent_has_no_sibling_visibility(runtime: Runtime) -> None:
    runtime.set_agent_factory(TrackingResearchAgent)

    root_task = Task(description="Root task")
    root = runtime.spawn_agent(root_task)

    child_a = root.spawn("Task A")
    child_b = root.spawn("Task B")

    assert not hasattr(child_a, "siblings")
    assert not hasattr(child_b, "siblings")
    assert not hasattr(child_a, "task_graph")
    assert not hasattr(child_b, "task_graph")
    assert hasattr(child_a, "parent")  # agent knows its parent


@pytest.mark.asyncio
async def test_report_creates_artifact_and_commit(runtime: Runtime) -> None:
    runtime.set_agent_factory(TrackingResearchAgent)

    root_task = Task(description="Generate artifact")
    root = runtime.spawn_agent(root_task)
    await root.run()

    assert runtime.repository.count() >= 1
    commits = runtime.repository.log()
    assert any(c.task_id == root_task.id for c in commits)