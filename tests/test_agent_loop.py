from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest

from dynamic_harness.core.agent import Agent
from dynamic_harness.core.runner import AgentRunner
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import ReportPayload, Task


@pytest.fixture
def runtime() -> Runtime:
    tmp = Path(tempfile.mkdtemp())
    return Runtime(artifact_root=tmp / "artifacts", repo_root=tmp / "repo")


@pytest.mark.asyncio
async def test_runner_runs_agent_to_completion(runtime: Runtime) -> None:
    runner = AgentRunner(runtime)
    runner.connect()
    await runner.run("test task")
    assert any("report done" in e for e in runner.events)
    assert len(runner.last_reports) >= 1


@pytest.mark.asyncio
async def test_runner_tracks_events_and_reports(runtime: Runtime) -> None:
    class LeafAgent(Agent):
        async def run(self) -> None:
            self.report(ReportPayload(
                task_id=self.task.id,
                summary="Leaf done",
            ))

    runtime.register_agent_class("LeafAgent", LeafAgent)
    runner = AgentRunner(runtime)
    runner.connect()
    root = runtime.spawn_agent(Task(description="test"), agent_type="LeafAgent")
    await runner.run_root(root)

    assert any("report done" in e for e in runner.events)
    assert any("Leaf" in summary for _, summary in runner.last_reports)


@pytest.mark.asyncio
async def test_runner_tracks_failure_events(runtime: Runtime) -> None:
    class FailingAgent(Agent):
        async def run(self) -> None:
            self.fail("oops")

    runtime.register_agent_class("FailingAgent", FailingAgent)
    runner = AgentRunner(runtime)
    runner.connect()
    root = runtime.spawn_agent(Task(description="fail"), agent_type="FailingAgent")
    await runner.run_root(root)

    assert any("fail: oops" in e for e in runner.events)
    assert root.task.status.value == "failed"


@pytest.mark.asyncio
async def test_runner_clear_events(runtime: Runtime) -> None:
    runner = AgentRunner(runtime)
    runner.events.append("stale event")
    runner.connect()
    await runner.run("test", clear_events=True)
    assert "stale event" not in runner.events
    assert any("report done" in e for e in runner.events)


@pytest.mark.asyncio
async def test_runner_does_not_clear_events_when_false(runtime: Runtime) -> None:
    runner = AgentRunner(runtime)
    runner.events.append("stale event")
    runner.connect()
    await runner.run("test", clear_events=False)
    assert "stale event" in runner.events


@pytest.mark.asyncio
async def test_runner_on_update_callback(runtime: Runtime) -> None:
    call_count = 0

    def on_update() -> None:
        nonlocal call_count
        call_count += 1

    runner = AgentRunner(runtime)
    runner.connect()
    await runner.run("quick task", on_update=on_update)
    assert call_count > 0


@pytest.mark.asyncio
async def test_runner_shutdown_event_stops_execution(runtime: Runtime) -> None:
    class SlowAgent(Agent):
        async def run(self) -> None:
            for _ in range(100):
                await asyncio.sleep(0.01)

    runtime.register_agent_class("SlowAgent", SlowAgent)
    runner = AgentRunner(runtime)
    runner.connect()

    shutdown = asyncio.Event()
    root = runtime.spawn_agent(Task(description="slow"), agent_type="SlowAgent")

    async def trigger_shutdown() -> None:
        await asyncio.sleep(0.05)
        shutdown.set()

    t1 = asyncio.ensure_future(trigger_shutdown())
    t2 = asyncio.ensure_future(runner.run_root(root, shutdown_event=shutdown))
    await asyncio.wait([t1, t2])

    assert root.task.status.value == "running"  # was cancelled mid-execution


@pytest.mark.asyncio
async def test_runner_reuse_across_multiple_runs(runtime: Runtime) -> None:
    runner = AgentRunner(runtime)
    runner.connect()
    await runner.run("first task")

    await runner.run("second task")
    assert len(runner.last_reports) >= 2
