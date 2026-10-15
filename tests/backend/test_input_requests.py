"""Unit tests for the external input channel (IMP-006).

Covers: request emission (event + queue), answer routing by id, timeout
hooks per request, the harness.json policy paths (assume_and_record /
default_answer / fail_fast), the request-flood guard, and the invariant
that an unanswered request never settles as pass.
"""

from __future__ import annotations

import asyncio

import pytest

from dynamic_harness.config import HarnessConfig, InputRequestConfig
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import (
    InputAnswer,
    InputRequest,
    Task,
    TaskStatus,
)
from dynamic_harness.llm.provider import LLMProvider, ToolCallData, ToolCallResponse


class _AskingLLM(LLMProvider):
    """One request_input tool-call, then a report carrying the answer."""

    def __init__(self, question: str, kind: str = "clarification") -> None:
        self.question = question
        self.kind = kind
        self.turn = 0
        self.answer = "blue"

    async def generate(self, system, user, config=None):
        raise NotImplementedError

    async def generate_with_tools(self, messages, tools, config=None):
        self.turn += 1
        if self.turn == 1:
            return ToolCallResponse(
                tool_calls=[ToolCallData(
                    id="c1", name="request_input",
                    arguments={"question": self.question, "kind": self.kind},
                )],
                content=None, model="mock",
            )
        return ToolCallResponse(
            tool_calls=None, content=f"done: {self.answer}", model="mock",
        )

    async def generate_structured(self, system, user, response_model, config=None):
        raise NotImplementedError


def _runtime(
    tmp_path,
    *,
    with_handler: bool = False,
    policy: str | None = None,
    timeout_seconds: float | None = None,
) -> Runtime:
    config = None
    if policy is not None or timeout_seconds is not None:
        cfg_kwargs: dict = {}
        if policy is not None:
            cfg_kwargs["policy"] = policy
        if timeout_seconds is not None:
            cfg_kwargs["timeout_seconds"] = timeout_seconds
        config = HarnessConfig(input_requests=InputRequestConfig(**cfg_kwargs))
    rt = Runtime(
        artifact_root=tmp_path / "artifacts", repo_root=tmp_path / "repo",
        generated_root=tmp_path, config=config,
    )
    if with_handler:
        # A registered answer source (terminal / outer harness) keeps the
        # request pending instead of settling it immediately.
        rt.event_bus.on_input_request(lambda aid, req: None)
    else:
        rt.set_llm(_AskingLLM("what color?"))
    return rt


# -- emission -----------------------------------------------------------------


async def test_request_emits_event_and_queues(tmp_path) -> None:
    rt = _runtime(tmp_path, with_handler=True)
    seen: list[InputRequest] = []
    rt.event_bus.on_input_request(lambda aid, req: seen.append(req))

    req = InputRequest(question="what color?", kind="decision", options=["a", "b"])
    fut = rt.request_input("agent-1", req)

    assert not fut.done()  # pending, not settled
    assert len(seen) == 1 and seen[0].id == req.id
    snap = rt.pending_input_requests()[0]
    assert snap["id"] == req.id and snap["kind"] == "decision"
    assert snap["options"] == ["a", "b"]


async def test_request_kind_is_validated(tmp_path) -> None:
    _runtime(tmp_path)
    with pytest.raises(Exception):
        InputRequest(question="q", kind="bogus")


# -- answer routing -----------------------------------------------------------


async def test_answer_routes_by_id_and_unblocks_tool(tmp_path) -> None:
    rt = _runtime(tmp_path, with_handler=True)
    req = InputRequest(question="what color?")
    fut = rt.request_input("agent-1", req)

    assert rt.answer_input(req.id, "blue") is True
    assert await asyncio.wait_for(fut, timeout=1) == "blue"
    assert rt.pending_input_requests() == []
    # Unknown / already-answered ids are dropped, not errors.
    assert rt.answer_input(req.id, "again") is False
    assert rt.answer_input("nope", "x") is False


async def test_answer_event_fires_on_resolution(tmp_path) -> None:
    rt = _runtime(tmp_path, with_handler=True)
    answers: list[InputAnswer] = []
    rt.event_bus.on_input_answer(lambda aid, ans: answers.append(ans))

    req = InputRequest(question="q?")
    rt.request_input("agent-1", req)
    rt.answer_input(req.id, "42", by="outer_harness")

    assert len(answers) == 1
    assert answers[0].request_id == req.id
    assert answers[0].value == "42"
    assert answers[0].by == "outer_harness"
    assert answers[0].assumed is False


# -- timeout hooks ------------------------------------------------------------


async def test_timeout_assume_and_record_marks_assumed(tmp_path) -> None:
    rt = _runtime(tmp_path, with_handler=True)
    answers: list[InputAnswer] = []
    rt.event_bus.on_input_answer(lambda aid, ans: answers.append(ans))

    req = InputRequest(question="q?", timeout=0.05, default="blue")
    rt.request_input("agent-1", req)
    await asyncio.sleep(0.15)

    assert rt.pending_input_requests() == []
    assert len(answers) == 1
    assert answers[0].value == "blue"
    assert answers[0].assumed is True  # recorded as an assumption


async def test_timeout_assume_without_default_answers_empty(tmp_path) -> None:
    rt = _runtime(tmp_path, with_handler=True)
    req = InputRequest(question="q?", timeout=0.05)
    rt.request_input("agent-1", req)
    await asyncio.sleep(0.15)
    assert rt.pending_input_requests() == []


async def test_timeout_fail_fast_fails_requesting_agent(tmp_path) -> None:
    rt = _runtime(tmp_path, with_handler=True, policy="fail_fast")
    agent = rt.delegate(Task(description="root"))
    req = InputRequest(question="q?", timeout=0.05)
    rt.request_input(agent.id, req)
    await asyncio.sleep(0.15)
    assert agent.last_failure is not None
    assert rt.pending_input_requests() == []


async def test_timeout_default_answer_without_default_fails(tmp_path) -> None:
    rt = _runtime(tmp_path, with_handler=True, policy="default_answer")
    agent = rt.delegate(Task(description="root"))
    req = InputRequest(question="q?", timeout=0.05)
    rt.request_input(agent.id, req)
    await asyncio.sleep(0.15)
    assert agent.last_failure is not None


async def test_config_timeout_caps_uncapped_requests(tmp_path) -> None:
    rt = _runtime(tmp_path, with_handler=True)
    req = InputRequest(question="q?")  # no per-request timeout
    rt.request_input("agent-1", req)
    await asyncio.sleep(0.15)
    # Default policy timeout_seconds=120 has not elapsed: still pending.
    assert len(rt.pending_input_requests()) == 1


# -- policy paths ---------------------------------------------------------------


async def test_policy_fail_fast_settles_immediately(tmp_path) -> None:
    rt = _runtime(tmp_path, with_handler=True, policy="fail_fast",
                  timeout_seconds=0.05)
    agent = rt.delegate(Task(description="root"))
    req = InputRequest(question="q?")  # no per-request timeout
    rt.request_input(agent.id, req)
    await asyncio.sleep(0.15)
    assert agent.last_failure is not None
    assert rt.pending_input_requests() == []


async def test_policy_default_answer_without_default_fails(tmp_path) -> None:
    rt = _runtime(tmp_path, with_handler=True, policy="default_answer",
                  timeout_seconds=0.05)
    agent = rt.delegate(Task(description="root"))
    req = InputRequest(question="q?")
    rt.request_input(agent.id, req)
    await asyncio.sleep(0.15)
    assert agent.last_failure is not None


async def test_policy_assume_and_record_answers_default(tmp_path) -> None:
    rt = _runtime(tmp_path, with_handler=True, policy="assume_and_record",
                  timeout_seconds=0.05)
    answers: list[InputAnswer] = []
    rt.event_bus.on_input_answer(lambda aid, ans: answers.append(ans))
    req = InputRequest(question="q?", default="proceed")
    rt.request_input("agent-1", req)
    await asyncio.sleep(0.15)
    assert rt.pending_input_requests() == []
    assert len(answers) == 1
    assert answers[0].value == "proceed"
    assert answers[0].assumed is True


# -- flood guard ---------------------------------------------------------------


async def test_flood_guard_refuses_beyond_max_pending(tmp_path) -> None:
    rt = _runtime(tmp_path, with_handler=True)
    refused: list[asyncio.Future] = []
    for i in range(10):  # default max_pending = 10
        fut = rt.request_input("agent-1", InputRequest(question=f"q{i}"))
        if fut.done():
            refused.append(fut)
    assert refused == []  # all 10 queued
    fut = rt.request_input("agent-1", InputRequest(question="q11"))
    assert fut.done() and fut.exception() is not None  # 11th refused
    assert len(rt.pending_input_requests()) == 10


# -- the never-pass invariant ---------------------------------------------------


async def test_unanswered_request_never_settles_as_pass(tmp_path) -> None:
    """With no answer source, the request settles per policy — recorded as an
    assumption or a failure, never as a pass."""
    rt = _runtime(tmp_path, with_handler=True, policy="assume_and_record",
                  timeout_seconds=0.05)
    agent = rt.delegate(Task(description="root"))
    req = InputRequest(question="q?", default="proceed")
    fut = rt.request_input(agent.id, req)
    await asyncio.sleep(0.15)
    # assume_and_record: settled as a recorded assumption, agent not passed.
    assert agent.last_report is None
    assert agent.last_failure is None
    assert await asyncio.wait_for(fut, timeout=1) == "proceed"


async def test_end_to_end_tool_round_trip(tmp_path) -> None:
    """The agent's request_input tool call blocks until the answer arrives,
    and the answer reaches the agent's context."""
    rt = _runtime(tmp_path)
    llm = rt._llm
    assert isinstance(llm, _AskingLLM)
    llm.answer = "blue"

    root = rt.delegate(Task(description="ask the user"))
    await asyncio.wait_for(rt.run("ask the user", root_agent=root), timeout=5)

    assert root.task.status.value == "completed"
    assert "done: blue" in root.last_report.summary



# -- IMP-006 push-answer regressions (trial findings BUG #3) ------------------


class _RecordingAskingLLM(_AskingLLM):
    """_AskingLLM that records the messages it sees, so a test can assert
    what the agent was actually told (the channel round-trip, not the mock's
    own echo)."""

    def __init__(self, question: str) -> None:
        super().__init__(question)
        self.seen: list[list[dict]] = []

    async def generate_with_tools(self, messages, tools, config=None):
        self.seen.append(list(messages))
        return await super().generate_with_tools(messages, tools, config)


async def test_sync_activity_handler_answer_reaches_agent(tmp_path) -> None:
    """BUG #3a regression: the INPUT_REQUEST activity event must fire only
    AFTER the runtime has registered the request as pending, so a
    synchronous activity-stream handler answering via ``answer_input``
    inside the event reaches the agent instead of being dropped.

    Pre-fix the event fired before the request was registered:
    ``answer_input`` returned False and the answer was silently lost (the
    tool call then failed)."""
    rt = _runtime(tmp_path, with_handler=True)
    seen: list[InputRequest] = []

    def _answer(aid: str, req: InputRequest) -> None:
        seen.append(req)
        assert rt.answer_input(req.id, "the pushed answer") is True

    rt.event_bus.on_activity(lambda ev: (
        _answer(ev.agent_id, InputRequest(**ev.data["request"]))
        if ev.event_type.value == "input_request" else None
    ))

    llm = _RecordingAskingLLM("what color?")
    llm.answer = "the pushed answer"
    rt.set_llm(llm)
    root = rt.delegate(Task(description="ask"))
    await asyncio.wait_for(rt.run("ask", root_agent=root), timeout=5)

    assert len(seen) == 1
    assert seen[0].question == "what color?"
    tool_msgs = [m for m in llm.seen[-1] if m.get("role") == "tool"]
    assert any("the pushed answer" in str(m.get("content", "")) for m in tool_msgs)
    assert not any("blue" in str(m.get("content", "")) for m in tool_msgs)
    assert "done: the pushed answer" in root.last_report.summary


async def test_bare_activity_handler_is_not_an_answer_source(tmp_path) -> None:
    """The no-source check counts the dedicated ``input_request`` channel —
    the answer surface — not the activity stream (an observability broadcast:
    the CLI and Harness internals always listen there without being able to
    answer). A bare activity handler therefore does NOT keep a request
    pending: with no answer source the request settles immediately per
    policy, preserving the batch non-blocking guarantee."""
    rt = _runtime(tmp_path, policy="assume_and_record", timeout_seconds=120.0)
    rt.event_bus.on_activity(lambda ev: None)  # bare activity listener

    agent = rt.delegate(Task(description="root"))
    req = InputRequest(question="q?", default="proceed")
    fut = rt.request_input(agent.id, req)
    assert fut.done()  # settled on the spot — no answer source exists
    assert await fut == "proceed"
    assert rt.pending_input_requests() == []


async def test_zero_handlers_still_settles_immediately(tmp_path) -> None:
    """The batch non-blocking guarantee: with NO answer source registered at
    all (no dedicated input_request handler, no activity handler), the
    request settles immediately per policy — a run never blocks on input
    nobody can give."""
    rt = _runtime(tmp_path, policy="assume_and_record", timeout_seconds=120.0)
    agent = rt.delegate(Task(description="root"))
    req = InputRequest(question="q?", default="fallback")
    fut = rt.request_input(agent.id, req)
    assert fut.done()  # settled on the spot, never blocks
    assert await fut == "fallback"
    assert rt.pending_input_requests() == []
