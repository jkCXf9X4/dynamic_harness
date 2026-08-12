from __future__ import annotations

import asyncio

import pytest

from dynamic_harness.core.agent import Agent
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import ReportPayload, Task


@pytest.mark.asyncio
async def test_runtime_run_returns_agent_and_fails_without_llm(runtime: Runtime) -> None:
    root = await runtime.run("test task")
    assert root.task.status.value == "failed"
    assert root.last_failure is not None
    assert "No LLM provider configured" in root.last_failure.error


@pytest.mark.asyncio
async def test_runtime_run_with_registered_agent(runtime: Runtime) -> None:
    class LeafAgent(Agent):
        async def run(self) -> None:
            self.report(ReportPayload(
                task_id=self.task.id,
                summary="Leaf done",
            ))

    runtime.register_agent_class("LeafAgent", LeafAgent)
    root = await runtime.run("test", agent_type="LeafAgent")

    assert root.task.status.value == "completed"
    assert root.last_report is not None
    assert "Leaf" in root.last_report.summary


@pytest.mark.asyncio
async def test_runtime_run_tracks_failure_outcome(runtime: Runtime) -> None:
    class FailingAgent(Agent):
        async def run(self) -> None:
            self.fail("oops")

    runtime.register_agent_class("FailingAgent", FailingAgent)
    root = await runtime.run("fail", agent_type="FailingAgent")

    assert root.last_failure is not None
    assert "oops" in root.last_failure.error
    assert root.task.status.value == "failed"


@pytest.mark.asyncio
async def test_runtime_run_resumes_root_agent(runtime: Runtime) -> None:
    class LeafAgent(Agent):
        async def run(self) -> None:
            self.report(ReportPayload(
                task_id=self.task.id,
                summary=f"iter: {self.task.description}",
            ))

    runtime.register_agent_class("LeafAgent", LeafAgent)
    root = await runtime.run("first", agent_type="LeafAgent")
    assert root.last_report is not None

    await runtime.run("second", root_agent=root)
    assert root.task.status.value == "completed"
    # continue_with_input appended a user message and the agent re-reported.
    assert root.last_report is not None


@pytest.mark.asyncio
async def test_runtime_run_reuse_creates_distinct_roots(runtime: Runtime) -> None:
    a = await runtime.run("task one")
    b = await runtime.run("task two")
    assert a.id != b.id
    assert runtime.agent_count() == 2


@pytest.mark.asyncio
async def test_cancel_via_task_cancellation(runtime: Runtime) -> None:
    class SlowAgent(Agent):
        async def run(self) -> None:
            for _ in range(100):
                await asyncio.sleep(0.01)

    runtime.register_agent_class("SlowAgent", SlowAgent)
    root = runtime.delegate(Task(description="slow"), agent_type="SlowAgent")

    run_task = asyncio.ensure_future(root.run())
    await asyncio.sleep(0.05)
    run_task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await run_task

    assert root.task.status.value == "running"
