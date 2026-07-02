from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from dynamic_harness.core.agent import Agent
from dynamic_harness.core.agent_examples import PlannerAgent, ResearchAgent
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import Task


class TrackingPlanner(PlannerAgent):
    def __init__(self, agent_id: str, task: Task, runtime: Runtime, parent: Agent | None = None) -> None:
        super().__init__(agent_id, task, runtime, parent)
        self.log: list[str] = []

    async def _decompose(self) -> list[str]:
        return ["Subtask 1", "Subtask 2"]

    async def _merge(self) -> object:
        from dynamic_harness.core.task import ReportPayload
        return ReportPayload(
            task_id=self.task.id,
            summary="Merged results from all subtasks",
            next_actions=[],
        )


def make_tracking_agent(agent_id: str, task: Task, runtime: Runtime, parent: Agent | None = None) -> Agent:
    if parent is None:
        return TrackingPlanner(agent_id, task, runtime, parent)
    return ResearchAgent(agent_id, task, runtime, parent)


@pytest.fixture
def runtime() -> Runtime:
    tmp = Path(tempfile.mkdtemp())
    return Runtime(artifact_root=tmp / "artifacts", repo_root=tmp / "repo")


@pytest.mark.asyncio
async def test_planner_decomposes_and_runs_subtasks(runtime: Runtime) -> None:
    runtime.set_agent_factory(make_tracking_agent)

    root_task = Task(description="Solve the problem")
    root = runtime.spawn_agent(root_task)
    await root.run()

    assert root.task.status.value == "completed"
    assert runtime.agent_count() >= 3


@pytest.mark.asyncio
async def test_full_recursive_hierarchy(runtime: Runtime) -> None:
    runtime.set_agent_factory(make_tracking_agent)

    root_task = Task(description="Analyze codebase")
    root = runtime.spawn_agent(root_task)
    await root.run()

    graph = runtime.task_graph()
    assert root.id in graph
    assert len(graph[root.id]) == 2

    commits = runtime.repository.log()
    assert len(commits) >= 1


@pytest.mark.asyncio
async def test_runtime_tracks_task_graph(runtime: Runtime) -> None:
    runtime.set_agent_factory(make_tracking_agent)

    root_task = Task(description="Root")
    root = runtime.spawn_agent(root_task)

    a = root.spawn("A")
    b = root.spawn("B")

    graph = runtime.task_graph()
    assert a.id in graph[root.id]
    assert b.id in graph[root.id]


@pytest.mark.asyncio
async def test_artifact_store_populated_on_report(runtime: Runtime) -> None:
    runtime.set_agent_factory(make_tracking_agent)

    root_task = Task(description="Populate artifacts")
    root = runtime.spawn_agent(root_task)
    await root.run()

    commits = runtime.repository.log()
    for c in commits:
        for aid in c.artifact_ids:
            art = runtime.artifact_store.get(aid)
            assert art is not None, f"Artifact {aid} not found in store"