from __future__ import annotations

import json

import pytest

from dynamic_harness.core.agent import Agent
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import ReportPayload, Task, TaskStatus
from dynamic_harness.llm.provider import LLMProvider, ToolCallData, ToolCallResponse


class _FailThenSucceedLLM(LLMProvider):
    """Fails on the first generation, reports a deliverable on the second."""

    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, system, user, config=None):
        raise NotImplementedError

    async def generate_with_tools(self, messages, tools, config=None):
        self.calls += 1
        if self.calls == 1:
            return ToolCallResponse(
                content=None, model="mock",
                tool_calls=[ToolCallData(id="c1", name="fail", arguments={"error": "first attempt exploded"})],
            )
        return ToolCallResponse(
            content=None, model="mock",
            tool_calls=[ToolCallData(
                id="c2", name="report",
                arguments={"summary": "done now", "files_written": ["/out.txt"]},
            )],
        )

    async def generate_structured(self, system, user, response_model, config=None):
        raise NotImplementedError


class _AlwaysFailLLM(LLMProvider):
    async def generate(self, system, user, config=None):
        raise NotImplementedError

    async def generate_with_tools(self, messages, tools, config=None):
        return ToolCallResponse(
            content=None, model="mock",
            tool_calls=[ToolCallData(id="c1", name="fail", arguments={"error": "always fails"})],
        )

    async def generate_structured(self, system, user, response_model, config=None):
        raise NotImplementedError


class EscalateAgent(Agent):
    async def run(self) -> None:
        self.escalate("blocked on a missing dependency")


def _parent_with_failed_child(runtime: Runtime) -> tuple[Agent, Agent]:
    parent = runtime.delegate(Task(description="parent"))
    child = parent.delegate("read the file and summarize")
    return parent, child


@pytest.mark.asyncio
async def test_parent_resumes_blunt_failure(runtime: Runtime) -> None:
    llm = _FailThenSucceedLLM()
    runtime.set_llm(llm)
    parent, child = _parent_with_failed_child(runtime)
    await child.run()
    assert child.task.status == TaskStatus.failed

    result = json.loads(await parent.resume_child(
        child.id, note="don't forget the deliverable file"
    ))

    assert result["healed"] is True
    assert result["status"] == "completed"
    assert result["diagnosis"] == "blunt"
    assert result["origin_agent_id"] == child.id
    assert result["agent_id"] == child.id  # in-memory resume keeps the same agent
    assert llm.calls == 2
    # the parent's note landed in the child's context before its recovery turn
    assert any(
        "don't forget the deliverable file" in str(m.get("content", ""))
        for m in child.context.messages
    )


@pytest.mark.asyncio
async def test_resume_tool_via_registry(runtime: Runtime) -> None:
    runtime.set_llm(_FailThenSucceedLLM())
    parent, child = _parent_with_failed_child(runtime)
    await child.run()

    result = await runtime.tool_registry.execute(
        "resume", "tc1", agent=parent,
        agent_id=child.id, strategy="automatic", note="retry",
    )
    payload = json.loads(result.content)
    assert payload["healed"] is True
    assert payload["status"] == "completed"


@pytest.mark.asyncio
async def test_resume_refuses_escalated_child(runtime: Runtime) -> None:
    runtime.register_agent_class("EscalateAgent", EscalateAgent)
    parent, child = _parent_with_failed_child(runtime)
    await child.run()
    # craft an escalated child deterministically
    other = runtime.delegate(
        Task(description="esc"), parent=parent, agent_type="EscalateAgent"
    )
    await other.run()
    assert other.task.status == TaskStatus.escalated

    result = json.loads(await parent.resume_child(other.id))
    assert "escalations are never resumed" in result["error"]


@pytest.mark.asyncio
async def test_resume_refuses_non_child(runtime: Runtime) -> None:
    runtime.set_llm(_FailThenSucceedLLM())
    parent, child = _parent_with_failed_child(runtime)
    sibling = parent.delegate("sibling")
    await child.run()

    result = json.loads(await sibling.resume_child(child.id))
    assert "not one of your direct children" in result["error"]


@pytest.mark.asyncio
async def test_resume_refuses_killed_child(runtime: Runtime) -> None:
    runtime.set_llm(_AlwaysFailLLM())
    parent, child = _parent_with_failed_child(runtime)
    await child.run()
    child._killed = True  # kill only marks *running* agents; simulate the flag

    result = json.loads(await parent.resume_child(child.id))
    assert "deliberately killed" in result["error"]


@pytest.mark.asyncio
async def test_resume_refuses_already_delivered(runtime: Runtime) -> None:
    class Completer(Agent):
        async def run(self) -> None:
            self.report(ReportPayload(
                task_id=self.task.id,
                summary="done",
                files_written=["/done.txt"],
            ))

    runtime.register_agent_class("Completer", Completer)
    parent = runtime.delegate(Task(description="parent"))
    child = parent.delegate("complete", agent_type="Completer")
    await child.run()
    assert child.task.status == TaskStatus.completed

    result = json.loads(await parent.resume_child(child.id))
    assert result["status"] == "already_delivered"


@pytest.mark.asyncio
async def test_resume_rot_spawns_fresh_worker(runtime: Runtime) -> None:
    runtime.set_llm(_FailThenSucceedLLM())
    parent, child = _parent_with_failed_child(runtime)
    await child.run()
    child._repeated_calls_detected = True  # rot: context itself is the problem

    result = json.loads(await parent.resume_child(child.id))
    effective = runtime.get_agent(result["agent_id"])

    assert result["diagnosis"] == "rot"
    assert result["healed"] is True
    assert effective is not None
    assert effective.id != child.id  # clean worker, not a context replay
    assert effective.parent is parent
    # the parent's children list now points at the effective agent
    assert any(c is effective for c in parent.children)
    assert result["heal_counts"]["fresh"] == 1


@pytest.mark.asyncio
async def test_fresh_worker_carries_parent_note(runtime: Runtime) -> None:
    runtime.set_llm(_FailThenSucceedLLM())
    parent, child = _parent_with_failed_child(runtime)
    await child.run()
    child._repeated_calls_detected = True

    result = json.loads(await parent.resume_child(
        child.id, strategy="fresh", note="write variants.json specifically"
    ))
    effective = runtime.get_agent(result["agent_id"])
    assert result["healed"] is True
    assert effective is not None
    assert "write variants.json specifically" in effective.task.description


@pytest.mark.asyncio
async def test_force_resume_refused_on_rot(runtime: Runtime) -> None:
    runtime.set_llm(_AlwaysFailLLM())
    parent, child = _parent_with_failed_child(runtime)
    await child.run()
    child._repeated_calls_detected = True

    result = json.loads(await parent.resume_child(child.id, strategy="resume"))
    assert result["status"] == "refused_rot"
    assert "would replay" in result["error"]


@pytest.mark.asyncio
async def test_force_fresh_ignores_rot(runtime: Runtime) -> None:
    runtime.set_llm(_FailThenSucceedLLM())
    parent, child = _parent_with_failed_child(runtime)
    await child.run()
    child._repeated_calls_detected = True

    result = json.loads(await parent.resume_child(child.id, strategy="fresh"))
    assert result["healed"] is True
    assert result["agent_id"] != child.id


@pytest.mark.asyncio
async def test_resume_budget_respected(runtime: Runtime) -> None:
    runtime._self_heal_max_resumes = 0  # no same-agent resume allowed
    runtime.set_llm(_FailThenSucceedLLM())
    parent, child = _parent_with_failed_child(runtime)
    await child.run()

    result = json.loads(await parent.resume_child(child.id))
    assert result["diagnosis"] == "blunt"
    assert result["heal_counts"]["resume"] == 0  # layer skipped, budget spent on fresh
    assert result["healed"] is True
    assert result["heal_counts"]["fresh"] == 1


@pytest.mark.asyncio
async def test_parent_resume_from_disk_rebuild_preserves_linkage(runtime: Runtime) -> None:
    """A garbage-collected (context-freed) child resumes from its checkpoint,
    getting a fresh agent id — the parent's children list must be re-pointed."""
    runtime.set_llm(_FailThenSucceedLLM())
    parent, child = _parent_with_failed_child(runtime)
    await child.run()
    assert child.collect_garbage()  # context freed -> Runtime.resume rebuilds from disk

    result = json.loads(await parent.resume_child(child.id))
    effective = runtime.get_agent(result["agent_id"])

    assert result["healed"] is True
    assert effective is not None
    assert effective.id != child.id
    assert effective.parent is parent
    assert any(c is effective for c in parent.children)
    # the very next resume/status on the recovered id is not confused
    status = json.loads(await parent.resume_child(effective.id))
    assert status["status"] == "already_delivered"