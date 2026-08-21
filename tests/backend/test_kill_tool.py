from __future__ import annotations

import asyncio
import json

import pytest

from dynamic_harness.core.agent import Agent
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import ReportPayload, Task, TaskStatus
from dynamic_harness.core.tool_context import ToolContext


class _SlowChild(Agent):
    async def run(self) -> None:
        try:
            await asyncio.sleep(30.0)
        except asyncio.CancelledError:
            if not self.last_report and not self.last_failure:
                self.fail("Agent cancelled")
            raise
        self.report(ReportPayload(
            task_id=self.task.id,
            summary="should never report",
        ))


@pytest.mark.asyncio
async def test_kill_cancels_running_child_and_marks_failed(runtime: Runtime) -> None:
    runtime.register_agent_class("SlowChild", _SlowChild)

    root = runtime.delegate(Task(description="root", role="orchestrator"))
    child = root.delegate("a slow subtask", agent_type="SlowChild")
    assert child.parent is root

    task = asyncio.create_task(child.run())
    runtime.set_agent_run_task(child.id, task)
    await asyncio.sleep(0.05)  # let the child enter its (blocked) run

    result = await root.kill(child.id, reason="no longer needed")
    assert child._killed is True
    assert child.task.status is TaskStatus.failed
    assert child.last_failure is not None
    assert "no longer needed" in child.last_failure.error
    assert child.last_report is None
    await asyncio.sleep(0.05)  # let cancellation propagate
    # the killed child never reached its (deliberately unreachable) report
    assert child.last_report is None
    assert child.last_failure is not None and child._killed


@pytest.mark.asyncio
async def test_kill_rejects_non_child_and_recurses(runtime) -> None:
    runtime.register_agent_class("SlowChild", _SlowChild)

    root = runtime.delegate(Task(description="root"))
    intruder = runtime.delegate(Task(description="intruder"))
    child = root.delegate("subtask", agent_type="SlowChild")
    grandchild = child.delegate("subsubtask", agent_type="SlowChild")

    t1 = asyncio.create_task(child.run())
    t2 = asyncio.create_task(grandchild.run())
    runtime.set_agent_run_task(child.id, t1)
    runtime.set_agent_run_task(grandchild.id, t2)
    await asyncio.sleep(0.05)

    # root cannot kill a sibling's child.
    out = await intruder.kill(child.id)
    assert "not one of your direct children" in out
    assert child._killed is False

    # root CAN kill its child and (recursively) its grandchild.
    await root.kill(child.id, recursive=True)
    assert child._killed is True and grandchild._killed is True

    # a killed agent is never resurrected by self-heal.
    healed = await runtime._recover(child)
    assert healed is child
    assert healed.last_failure is not None


@pytest.mark.asyncio
async def test_kill_prevents_self_heal_resurrection(runtime) -> None:
    runtime.register_agent_class("SlowChild", _SlowChild)
    root = runtime.delegate(Task(description="root"))
    child = root.delegate("subtask", agent_type="SlowChild")

    task = asyncio.create_task(child.run())
    runtime.set_agent_run_task(child.id, task)
    await asyncio.sleep(0.05)

    killed = runtime.kill_agent(child.id, reason="stop")
    assert killed == {child.id}
    # even a fresh worker must NOT be spawned for a killed agent
    healed = await runtime._recover(child)
    assert healed is child
    await asyncio.sleep(0.05)
    assert child.last_report is None
    assert child.last_failure is not None


class _SalvageChild(Agent):
    async def run(self) -> None:
        self.set_plan(steps=["inspect input", "transform data", "write output"])
        self.mark_focus_done("inspect input")
        self.context.messages.append({"role": "user", "content": "inspect the source"})
        self.context.append({"role": "assistant", "content": "inspected: found 3 edge cases"})
        self.checkpoint("finished inspection, about to transform")
        self.fail("transform step errored")


class _PartialBlockedChild(Agent):
    async def run(self) -> None:
        self.set_plan(steps=["inspect input", "transform data", "write output"])
        self.mark_focus_done("inspect input")
        # seed messages the standard run() would create (user then assistant/tool)
        self.context.messages.append({"role": "user", "content": "inspect the source"})
        self.context.append({
            "role": "assistant",
            "content": "inspected source; found the bug is in eager loading",
        })
        self.context.append({
            "role": "tool",
            "content": "grep: eager=True at src/app.py:44",
        })
        self.checkpoint("inspection done; about to transform")
        try:
            await asyncio.sleep(30.0)
        except asyncio.CancelledError:
            if not self.last_report and not self.last_failure:
                self.fail("Agent cancelled")
            raise


@pytest.mark.asyncio
async def test_status_tool_reports_running_and_failed_children(runtime: Runtime) -> None:
    runtime.register_agent_class("SlowChild", _SlowChild)
    runtime.register_agent_class("SalvageChild", _SalvageChild)

    root = runtime.delegate(Task(description="root", role="orchestrator"))
    running = root.delegate("slow", agent_type="SlowChild")
    dead = root.delegate("failed subtask", agent_type="SalvageChild")

    task = asyncio.create_task(running.run())
    runtime.set_agent_run_task(running.id, task)
    task2 = asyncio.create_task(dead.run())
    runtime.set_agent_run_task(dead.id, task2)
    await asyncio.sleep(0.05)

    snapshots = json.loads(await ToolContext(root).status())  # via ToolContext
    assert isinstance(snapshots, list) and len(snapshots) == 2

    by_id = {s["agent_id"]: s for s in snapshots}
    assert by_id[dead.id]["status"] == "failed"
    assert "killed" in by_id[dead.id]["summary"] or "errored" in by_id[dead.id]["summary"]
    dead_shot = by_id[dead.id]
    assert dead_shot["plan"]["done"] == ["inspect input"]
    assert "transform data" in dead_shot["plan"]["pending"]
    assert "3 edge cases" in dead_shot["partial_data"]

    assert by_id[running.id]["status"] == "running"


@pytest.mark.asyncio
async def test_status_rejects_non_child(runtime) -> None:
    root = runtime.delegate(Task(description="root"))
    intruder = runtime.delegate(Task(description="intruder"))
    not_child = root.delegate("root's own child")
    out = await ToolContext(intruder).status(not_child.id)  # not a child of intruder
    assert "not one of your direct children" in out


@pytest.mark.asyncio
async def test_kill_result_embeds_salvaged_partial_data(runtime) -> None:
    runtime.register_agent_class("PartialBlockedChild", _PartialBlockedChild)
    root = runtime.delegate(Task(description="root"))
    child = root.delegate("subtask", agent_type="PartialBlockedChild")

    task = asyncio.create_task(child.run())
    runtime.set_agent_run_task(child.id, task)
    await asyncio.sleep(0.05)

    result = json.loads(await root.kill(child.id, reason="retry it"))
    assert "retry it" in result["salvage"][child.id]["summary"]
    assert result["salvage"][child.id]["plan"]["done"] == ["inspect input"]
    assert "transform data" in result["salvage"][child.id]["plan"]["pending"]
    assert "eager loading" in result["salvage"][child.id]["partial_data"]