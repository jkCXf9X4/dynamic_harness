from __future__ import annotations

import asyncio

import pytest

from dynamic_harness.core.agent import Agent
from dynamic_harness.core.runner import AgentRunner
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import ReportPayload, Task


@pytest.mark.asyncio
async def test_runner_runs_agent_to_completion(runtime: Runtime) -> None:
    runner = AgentRunner(runtime)
    await runner.run("test task")
    assert any("fail:" in e for e in runner.events)
    assert len(runner.events) >= 1


@pytest.mark.asyncio
async def test_runner_tracks_events_and_reports(runtime: Runtime) -> None:
    class LeafAgent(Agent):
        async def run(self) -> None:
            self.report(ReportPayload(
                task_id=self.task.id,
                summary="Leaf done",
            ))

    runtime.register_agent_class("LeafAgent", LeafAgent)
    task = Task(description="test")
    root = runtime.delegate(task, agent_type="LeafAgent")
    await root.run()

    assert root._last_report is not None
    assert "Leaf" in root._last_report.summary


@pytest.mark.asyncio
async def test_runner_tracks_failure_events(runtime: Runtime) -> None:
    class FailingAgent(Agent):
        async def run(self) -> None:
            self.fail("oops")

    runtime.register_agent_class("FailingAgent", FailingAgent)
    task = Task(description="fail")
    root = runtime.delegate(task, agent_type="FailingAgent")
    await root.run()

    assert root._last_failure is not None
    assert "oops" in root._last_failure.error
    assert root.task.status.value == "failed"


@pytest.mark.asyncio
async def test_runner_clear_events(runtime: Runtime) -> None:
    runner = AgentRunner(runtime)
    runner.events.append("stale event")
    await runner.run("test", clear_events=True)
    assert "stale event" not in runner.events
    assert any("fail:" in e for e in runner.events)


@pytest.mark.asyncio
async def test_runner_does_not_clear_events_when_false(runtime: Runtime) -> None:
    runner = AgentRunner(runtime)
    runner.events.append("stale event")
    await runner.run("test", clear_events=False)
    assert "stale event" in runner.events


@pytest.mark.asyncio
async def test_runner_cancel_via_task_cancellation(runtime: Runtime) -> None:
    class SlowAgent(Agent):
        async def run(self) -> None:
            for _ in range(100):
                await asyncio.sleep(0.01)

    runtime.register_agent_class("SlowAgent", SlowAgent)
    task = Task(description="slow")
    root = runtime.delegate(task, agent_type="SlowAgent")

    run_task = asyncio.ensure_future(root.run())
    await asyncio.sleep(0.05)
    run_task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await run_task

    assert root.task.status.value == "running"


@pytest.mark.asyncio
async def test_runner_reuse_across_multiple_runs(runtime: Runtime) -> None:
    runner = AgentRunner(runtime)
    await runner.run("first task")
    await runner.run("second task", clear_events=False)
    assert len(runner.events) == 2
    assert all("fail:" in e for e in runner.events)
