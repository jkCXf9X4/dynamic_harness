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
async def test_meta_agent_generates_and_spawns(runtime: Runtime) -> None:
    root_task = Task(description="Create an agent that audits Python code")
    root = runtime.spawn_agent(root_task)
    await root.run()

    assert root.task.status.value == "completed"
    assert runtime.agent_count() >= 2


@pytest.mark.asyncio
async def test_generated_agent_class_is_registered(runtime: Runtime) -> None:
    root_task = Task(description="Create a DocAgent that generates documentation")
    root = runtime.spawn_agent(root_task)
    await root.run()

    assert any(k for k in runtime._agent_registry.keys())


@pytest.mark.asyncio
async def test_registered_agent_can_spawn_from_registry(runtime: Runtime) -> None:
    class LeafAgent(Agent):
        async def run(self) -> None:
            self.report(ReportPayload(
                task_id=self.task.id,
                summary="Leaf complete",
            ))

    runtime.register_agent_class("LeafAgent", LeafAgent)

    class RootAgent(Agent):
        async def run(self) -> None:
            child = self.spawn("Leaf task", agent_type="LeafAgent")
            await child.run()
            self.report(ReportPayload(
                task_id=self.task.id,
                summary="Root complete",
            ))

    runtime.register_agent_class("RootAgent", RootAgent)

    root = runtime.spawn_agent(Task(description="Root"), agent_type="RootAgent")
    await root.run()

    assert root.task.status.value == "completed"


@pytest.mark.asyncio
async def test_meta_agent_creates_file_on_disk(runtime: Runtime) -> None:
    root_task = Task(description="Create a TestRunnerAgent")
    root = runtime.spawn_agent(root_task)
    await root.run()

    py_files = list(runtime.generated_root.glob("*.py"))
    assert len(py_files) >= 1


@pytest.mark.asyncio
async def test_fallback_code_generates_valid_class(runtime: Runtime) -> None:
    from dynamic_harness.core.meta_agent import MetaAgent

    agent = MetaAgent("test", Task(description="Test"), runtime)
    class_name, code = await agent._generate_agent_code()
    assert class_name == "GeneratedAgent"
    assert "class GeneratedAgent(Agent):" in code
    assert "async def run" in code