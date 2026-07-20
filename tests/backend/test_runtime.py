from __future__ import annotations

import pytest

from dynamic_harness.core.agent import Agent
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import ReportPayload, Task


@pytest.mark.asyncio
async def test_default_agent_runtime(runtime: Runtime) -> None:
    root_task = Task(description="Default agent test")
    root = runtime.delegate(root_task)
    await root.run()

    assert root.task.status.value == "failed"
    assert "No LLM provider configured" in root._last_failure.error
    assert runtime.agent_count() >= 1


@pytest.mark.asyncio
async def test_runtime_tracks_task_graph(runtime: Runtime) -> None:
    class LeafAgent(Agent):
        async def run(self) -> None:
            self.report(ReportPayload(
                task_id=self.task.id,
                summary="Leaf done",
            ))

    runtime.register_agent_class("LeafAgent", LeafAgent)

    root = runtime.delegate(Task(description="Root"), agent_type="LeafAgent")
    a = root.delegate("A", agent_type="LeafAgent")
    b = root.delegate("B", agent_type="LeafAgent")

    graph = runtime.task_graph()
    assert a.id in graph[root.id]
    assert b.id in graph[root.id]


@pytest.mark.asyncio
async def test_artifact_store_populated_on_report(runtime: Runtime) -> None:
    class LeafAgent(Agent):
        async def run(self) -> None:
            self.report(ReportPayload(
                task_id=self.task.id,
                summary="Populated",
            ))

    runtime.register_agent_class("LeafAgent", LeafAgent)

    root = runtime.delegate(Task(description="Populate"), agent_type="LeafAgent")
    await root.run()

    commits = runtime.repository.log()
    for c in commits:
        for aid in c.artifact_ids:
            art = runtime.artifact_store.get(aid)
            assert art is not None, f"Artifact {aid} not found in store"


@pytest.mark.asyncio
async def test_runtime_event_handlers(runtime: Runtime) -> None:
    events: list[str] = []

    runtime.on_report(lambda aid, p: events.append(f"report:{aid[:8]}"))
    runtime.on_failure(lambda aid, f: events.append(f"fail:{aid[:8]}"))

    class LeafAgent(Agent):
        async def run(self) -> None:
            self.report(ReportPayload(
                task_id=self.task.id,
                summary="Test events",
            ))

    runtime.register_agent_class("LeafAgent", LeafAgent)
    root = runtime.delegate(Task(description="Events"), agent_type="LeafAgent")
    await root.run()

    assert any("report:" in e for e in events)


@pytest.mark.asyncio
async def test_unknown_agent_type_uses_default(runtime: Runtime) -> None:
    root = runtime.delegate(Task(description="Unknown type"), agent_type="Anything")
    await root.run()
    assert root.task.status.value == "failed"
    assert runtime.agent_count() >= 1
