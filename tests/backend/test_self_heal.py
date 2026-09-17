from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from dynamic_harness.config import HarnessConfig, SafetyConfig
from dynamic_harness.core.agent import Agent
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import ReportPayload, Task, TaskStatus
from dynamic_harness.llm.provider import LLMProvider, ToolCallData, ToolCallResponse


class _FailThenSucceedLLM(LLMProvider):
    """Fails on the first generation, completes with a deliverable later."""

    def __init__(self) -> None:
        self.calls = 0
        self.heal_events: list[dict] = []

    async def generate(self, system: str, user: str, config=None):
        raise NotImplementedError

    async def generate_with_tools(self, messages: list[dict], tools: list[dict], config=None):
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


class _EscalateLLM(LLMProvider):
    async def generate(self, system, user, config=None):
        raise NotImplementedError

    async def generate_with_tools(self, messages, tools, config=None):
        return ToolCallResponse(
            content=None, model="mock",
            tool_calls=[ToolCallData(id="c1", name="escalate", arguments={"issue": "blocked on missing API"})],
        )

    async def generate_structured(self, system, user, response_model, config=None):
        raise NotImplementedError


class _RotThenCompleteLLM(LLMProvider):
    """Repeats one tool call `rot_calls` times (rot), then completes."""

    def __init__(self, rot_calls: int) -> None:
        self.rot_calls = rot_calls
        self.calls = 0

    async def generate(self, system, user, config=None):
        raise NotImplementedError

    async def generate_with_tools(self, messages, tools, config=None):
        self.calls += 1
        if self.calls <= self.rot_calls:
            return ToolCallResponse(
                content=None, model="mock",
                tool_calls=[ToolCallData(id=f"c{self.calls}", name="read", arguments={"path": "/x.txt"})],
            )
        return ToolCallResponse(content="finished", model="mock")

    async def generate_structured(self, system, user, response_model, config=None):
        raise NotImplementedError


@pytest.mark.asyncio
async def test_layer1_resume_heals_blunt_failure(runtime: Runtime) -> None:
    llm = _FailThenSucceedLLM()
    runtime.set_llm(llm)
    runtime.on_activity(lambda e: llm.heal_events.append(e.data) if e.event_type.value == "self_heal" else None)

    root = await runtime.run("do the thing")

    assert root.task.status == TaskStatus.completed
    assert root.last_report is not None
    assert "done now" in root.last_report.summary
    assert llm.calls == 2  # original attempt + one resume
    actions = [e["action"] for e in llm.heal_events]
    assert actions == ["resume"]


class _ProseThenDeliverLLM(LLMProvider):
    """First reports prose with no deliverable, then reports with a file."""

    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, system, user, config=None):
        raise NotImplementedError

    async def generate_with_tools(self, messages, tools, config=None):
        self.calls += 1
        if self.calls == 1:
            return ToolCallResponse(
                content=None, model="mock",
                tool_calls=[ToolCallData(id="c1", name="report", arguments={"summary": "here are the findings"})],
            )
        return ToolCallResponse(
            content=None, model="mock",
            tool_calls=[ToolCallData(
                id="c2", name="report",
                arguments={"summary": "written now", "files_written": ["/out.txt"]},
            )],
        )

    async def generate_structured(self, system, user, response_model, config=None):
        raise NotImplementedError


@pytest.mark.asyncio
async def test_reported_but_no_deliverable_is_healed(runtime: Runtime) -> None:
    llm = _ProseThenDeliverLLM()
    runtime.set_llm(llm)
    events: list[dict] = []
    runtime.on_activity(lambda e: events.append(e.data) if e.event_type.value == "self_heal" else None)

    root = await runtime.run("produce a report")

    assert root.last_report is not None
    assert root.last_report.files_written  # healed with an on-disk deliverable
    assert llm.calls == 2
    actions = [e["action"] for e in events]
    assert actions == ["resume"]


class _DeliverWithOutputsLLM(LLMProvider):
    """Reports prose first, then writes the expected output file and reports."""

    def __init__(self, out_path: Path) -> None:
        self.out_path = out_path
        self.calls = 0

    async def generate(self, system, user, config=None):
        raise NotImplementedError

    async def generate_with_tools(self, messages, tools, config=None):
        self.calls += 1
        if self.calls == 1:
            return ToolCallResponse(
                content=None, model="mock",
                tool_calls=[ToolCallData(id="c1", name="report", arguments={"summary": "prose, no file"})],
            )
        if self.calls == 2:
            return ToolCallResponse(
                content=None, model="mock",
                tool_calls=[ToolCallData(id="c2", name="write", arguments={"path": str(self.out_path), "content": "[]"})],
            )
        return ToolCallResponse(
            content=None, model="mock",
            tool_calls=[ToolCallData(
                id="c3", name="report",
                arguments={"summary": "done", "files_written": [str(self.out_path)]},
            )],
        )

    async def generate_structured(self, system, user, response_model, config=None):
        raise NotImplementedError


@pytest.mark.asyncio
async def test_missing_expected_output_is_healed(runtime: Runtime, tmp: Path) -> None:
    out = tmp / "variants.json"
    llm = _DeliverWithOutputsLLM(out)
    runtime.set_llm(llm)
    events: list[dict] = []
    runtime.on_activity(lambda e: events.append(e.data) if e.event_type.value == "self_heal" else None)

    root = await runtime.run("write variants", expected_outputs=[str(out)])

    assert out.exists()  # heal wrote the real file
    assert root.last_report is not None
    actions = [e["action"] for e in events]
    assert actions == ["resume"]


@pytest.mark.asyncio
async def test_no_heal_without_llm(runtime: Runtime) -> None:
    root = await runtime.run("nothing configured")

    assert root.task.status == TaskStatus.failed
    assert root.last_failure is not None
    assert "No LLM provider configured" in root.last_failure.error


@pytest.mark.asyncio
async def test_escalation_is_not_healed(runtime: Runtime) -> None:
    runtime.set_llm(_EscalateLLM())

    root = await runtime.run("task")

    assert root.task.status == TaskStatus.escalated
    assert root.last_escalation is not None


@pytest.mark.asyncio
async def test_rot_triggers_fresh_worker(runtime: Runtime) -> None:
    # 3 identical calls raises repeated_call_limit (rot); fresh worker completes.
    llm = _RotThenCompleteLLM(rot_calls=3)
    runtime.set_llm(llm)
    runtime._repeated_call_limit = 3
    events: list[dict] = []
    runtime.on_activity(lambda e: events.append(e.data) if e.event_type.value == "self_heal" else None)

    root = await runtime.run("loopy task")

    assert root.task.status == TaskStatus.completed
    assert root.last_report is not None
    # original + fresh worker both registered
    assert runtime.agent_count() >= 2
    actions = [e["action"] for e in events]
    assert actions[0] == "fresh"


@pytest.mark.asyncio
async def test_fresh_worker_preserves_agent_type(runtime: Runtime) -> None:
    class Completer(Agent):
        async def run(self) -> None:
            self.report(self._mk())
        def _mk(self):
            from dynamic_harness.core.task import ReportPayload
            return ReportPayload(task_id=self.task.id, summary="custom done")

    class Failing(Agent):
        async def run(self) -> None:
            self.fail("custom fail")

    runtime.register_agent_class("Completer", Completer)
    runtime.register_agent_class("Failing", Failing)
    # A custom agent that fails the first run and the fresh restart uses same
    # type — here we verify agent_type is preserved on restart by using a
    # custom failing class whose fresh restart is also failing (kept bounded).
    runtime.set_llm(_FailThenSucceedLLM())
    root = await runtime.run("x", agent_type="Failing")
    # no LLM-driven progress on a fully custom run; just ensure no crash
    assert root is not None
    assert root.agent_type == "Failing"


@pytest.mark.asyncio
async def test_layer1_budget_exhausted_uses_fresh_then_stops(runtime: Runtime) -> None:
    # Every attempt fails immediately -> blunt resume once, then fresh, then stop.
    class AlwaysFail(Agent):
        async def run(self) -> None:
            self.fail("always fails")

    runtime.register_agent_class("AlwaysFail", AlwaysFail)
    runtime.set_llm(_FailThenSucceedLLM())
    events: list[dict] = []
    runtime.on_activity(lambda e: events.append(e.data) if e.event_type.value == "self_heal" else None)

    root = await runtime.run("t", agent_type="AlwaysFail")

    assert root.task.status == TaskStatus.failed
    actions = [e["action"] for e in events]
    assert actions == ["resume", "fresh"]


class _TimesOutOnceLLM(LLMProvider):
    """First call hangs past the wall-clock budget (timeout), then succeeds."""

    def __init__(self, hang: float) -> None:
        self.hang = hang
        self.calls = 0

    async def generate(self, system, user, config=None):
        raise NotImplementedError

    async def generate_with_tools(self, messages, tools, config=None):
        self.calls += 1
        if self.calls == 1:
            await asyncio.sleep(self.hang)  # exceeds safety.timeout_seconds
            return ToolCallResponse(content="too late", model="mock")
        return ToolCallResponse(
            content=None, model="mock",
            tool_calls=[ToolCallData(
                id="c2", name="report",
                arguments={"summary": "done after resume", "files_written": ["/out.txt"]},
            )],
        )

    async def generate_structured(self, system, user, response_model, config=None):
        raise NotImplementedError


def _runtime_with_timeout(tmp: Path, timeout: float = 0.3) -> Runtime:
    """A runtime whose agents all inherit a tight wall-clock budget (roots too,
    so a directly-delegated child can be driven to timeout in tests)."""
    cfg = HarnessConfig(
        safety=SafetyConfig(timeout_seconds=timeout, disable_root_timeout=False)
    )
    return Runtime(artifact_root=tmp / "artifacts", repo_root=tmp / "repo", generated_root=tmp, config=cfg)


async def _run_to_timeout(runtime: Runtime, hang: float = 5.0) -> Agent:
    """Delegate and run an agent whose LLM call hangs far beyond the budget,
    so it force-fails with a wall-clock timeout. Returns the failed agent."""
    agent = runtime.delegate(Task(description="slow child"))
    await agent.run()
    assert agent.task.status is TaskStatus.failed
    assert agent.last_failure is not None
    assert "timed out" in agent.last_failure.error
    return agent


@pytest.mark.asyncio
async def test_timeout_is_blunt_not_rot(tmp: Path) -> None:
    """A wall-clock timeout exhausts the budget, not the context: it is blunt,
    so a parent may resume the SAME child (`strategy="resume"` is legal on it)."""
    runtime = _runtime_with_timeout(tmp)
    runtime.set_llm(_TimesOutOnceLLM(hang=5.0))

    agent = await _run_to_timeout(runtime)

    assert agent._timed_out is True
    assert agent.is_rot() is False
    assert runtime.heal_diagnosis(agent) == "blunt"


@pytest.mark.asyncio
async def test_timeout_is_never_self_healed(tmp: Path) -> None:
    """Runtime._recover must leave a timed-out agent untouched: no resume, no
    fresh worker, no self-heal events — the decision stays with the parent."""
    runtime = _runtime_with_timeout(tmp)
    runtime.set_llm(_TimesOutOnceLLM(hang=5.0))
    events: list[dict] = []
    runtime.on_activity(lambda e: events.append(e.data) if e.event_type.value == "self_heal" else None)

    agent = await _run_to_timeout(runtime)
    before = runtime.agent_count()

    recovered = await runtime._recover(agent)

    assert recovered is agent  # untouched — no heal applied
    assert agent.task.status is TaskStatus.failed
    assert events == []  # no self-heal events at all
    assert runtime.agent_count() == before  # no fresh worker spawned


@pytest.mark.asyncio
async def test_timeout_parent_can_resume_same_child(tmp: Path) -> None:
    """The parent-level surface (`Runtime.resume`) continues a timed-out child:
    same context, fresh wall-clock budget, to a real deliverable."""
    runtime = _runtime_with_timeout(tmp)
    llm = _TimesOutOnceLLM(hang=5.0)
    runtime.set_llm(llm)

    child = await _run_to_timeout(runtime)
    assert child._timed_out is True

    resumed = await runtime.resume(child.id, message="continue the work")

    assert resumed.task.status is TaskStatus.completed
    assert resumed.last_report is not None
    assert resumed.last_report.files_written  # delivered after the resume
    assert llm.calls == 2  # original attempt + one continued run
    assert resumed is child  # same agent continued in place (context intact)
    assert resumed._timed_out is False  # a fresh budget cleared the stop marker


@pytest.mark.asyncio
async def test_timeout_parent_faces_resume_directions(tmp: Path) -> None:
    """The failure surfaced to the parent (delegate result + status snapshot)
    carries explicit directions for resuming the timed-out child."""
    runtime = _runtime_with_timeout(tmp)
    runtime.set_llm(_TimesOutOnceLLM(hang=5.0))

    child = await _run_to_timeout(runtime)
    parent = runtime.delegate(Task(description="parent"))
    parent.children.append(child)
    child.parent = parent

    # delegate-style result: the failure field embeds the resume directions
    result = json.loads(parent._format_delegate_result(child))
    assert 'strategy="resume"' in result["failure"]
    assert 'strategy="fresh"' in result["failure"]
    assert "NOT auto-retried" in result["failure"]

    # status snapshot: timed_out flag, not auto-recoverable, hint with directions
    snap = child.runtime_snapshot()
    assert snap["timed_out"] is True
    assert snap["heal"]["recoverable"] is False
    hint = snap["heal"]["resume_hint"]
    assert hint is not None
    assert f'agent_id="{child.id}"' in hint
    assert 'strategy="resume"' in hint


def test_fresh_restart_carries_mission_command_brief(runtime: Runtime) -> None:
    """A fresh self-heal worker is a replacement for the SAME mission: it must
    keep the parent's intent/end_state/constraints/authority, not restart cold."""
    task = Task(
        description="audit auth",
        intent="the release depends on auth being trustworthy",
        end_state="a verdict per finding in audit.md",
        constraints=["do not modify code"],
        authority="adapt the checks; report deviations",
    )
    agent = runtime.delegate(task)
    agent.fail("first attempt exploded")
    fresh = runtime._fresh_restart(agent)
    assert fresh is not None
    assert fresh.task.intent == task.intent
    assert fresh.task.end_state == task.end_state
    assert fresh.task.constraints == task.constraints
    assert fresh.task.authority == task.authority
    assert task.description in fresh.task.description
