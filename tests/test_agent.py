from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from dynamic_harness.core.agent import Agent
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import ReportPayload, Task


@pytest.fixture
def runtime() -> Runtime:
    tmp = Path(tempfile.mkdtemp())
    return Runtime(artifact_root=tmp / "artifacts", repo_root=tmp / "repo", generated_root=tmp / "gen")


@pytest.mark.asyncio
async def test_metaagent_spawns_and_completes(runtime: Runtime) -> None:
    root_task = Task(description="Test task")
    root = runtime.spawn_agent(root_task)
    await root.run()

    assert root.task.status.value == "completed"
    assert runtime.agent_count() >= 2


@pytest.mark.asyncio
async def test_agent_hierarchy_via_registry(runtime: Runtime) -> None:
    class LeafAgent(Agent):
        async def run(self) -> None:
            self.report(ReportPayload(
                task_id=self.task.id,
                summary=f"Leaf done: {self.task.description}",
            ))

    class BranchAgent(Agent):
        async def run(self) -> None:
            children = [
                self.spawn("Leaf A", agent_type="LeafAgent"),
                self.spawn("Leaf B", agent_type="LeafAgent"),
            ]
            for c in children:
                await c.run()
            self.report(ReportPayload(
                task_id=self.task.id,
                summary="Branch done",
            ))

    runtime.register_agent_class("LeafAgent", LeafAgent)
    runtime.register_agent_class("BranchAgent", BranchAgent)

    root_task = Task(description="Root")
    root = runtime.spawn_agent(root_task, agent_type="BranchAgent")
    await root.run()

    assert root.task.status.value == "completed"
    assert len(root.children) == 2
    graph = runtime.task_graph()
    assert root.id in graph
    assert len(graph[root.id]) == 2


@pytest.mark.asyncio
async def test_agent_failure(runtime: Runtime) -> None:
    class FailingAgent(Agent):
        async def run(self) -> None:
            try:
                raise RuntimeError("Intentional failure")
            except Exception as e:
                self.fail(str(e))

    runtime.register_agent_class("FailingAgent", FailingAgent)
    root = runtime.spawn_agent(Task(description="Fail"), agent_type="FailingAgent")
    await root.run()

    assert root.task.status.value == "failed"


@pytest.mark.asyncio
async def test_agent_has_no_sibling_visibility(runtime: Runtime) -> None:
    class LeafAgent(Agent):
        async def run(self) -> None:
            self.report(ReportPayload(
                task_id=self.task.id,
                summary="Leaf done",
            ))

    runtime.register_agent_class("LeafAgent", LeafAgent)

    root = runtime.spawn_agent(Task(description="Root"), agent_type="LeafAgent")
    child_a = root.spawn("Task A", agent_type="LeafAgent")
    child_b = root.spawn("Task B", agent_type="LeafAgent")

    assert not hasattr(child_a, "siblings")
    assert not hasattr(child_b, "siblings")
    assert not hasattr(child_a, "task_graph")
    assert not hasattr(child_b, "task_graph")
    assert hasattr(child_a, "parent")
    assert child_a.parent is root


@pytest.mark.asyncio
async def test_report_creates_artifact_and_commit(runtime: Runtime) -> None:
    class LeafAgent(Agent):
        async def run(self) -> None:
            self.report(ReportPayload(
                task_id=self.task.id,
                summary="Done",
            ))

    runtime.register_agent_class("LeafAgent", LeafAgent)
    root = runtime.spawn_agent(Task(description="Report"), agent_type="LeafAgent")
    await root.run()

    assert runtime.repository.count() >= 1
    commits = runtime.repository.log()
    assert any(c.task_id == root.task.id for c in commits)


@pytest.mark.asyncio
async def test_agent_guidelines_property(runtime: Runtime) -> None:
    class TestAgent(Agent):
        async def run(self) -> None:
            assert "self.spawn" in self.guidelines
            assert "self.report" in self.guidelines
            self.report(ReportPayload(
                task_id=self.task.id,
                summary="Guidelines OK",
            ))

    runtime.register_agent_class("TestAgent", TestAgent)
    root = runtime.spawn_agent(Task(description="Check"), agent_type="TestAgent")
    await root.run()
    assert root.task.status.value == "completed"