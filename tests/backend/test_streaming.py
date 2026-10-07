from __future__ import annotations

import asyncio

import pytest

from dynamic_harness.core.agent import Agent
from dynamic_harness.config import AgentConfig, HarnessConfig
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import ReportPayload, Task
from dynamic_harness.llm.provider import LLMProvider, ToolCallData, ToolCallResponse


# ── Streaming mock LLM ────────────────────────────────────────────────

class _RecordingLLM(LLMProvider):
    """Returns a scripted response sequence; records every message batch it sees
    so a test can assert what the parent was shown at each turn."""

    def __init__(self, responses: list[ToolCallResponse]) -> None:
        self.responses = responses
        self.idx = 0
        self.seen: list[list[dict]] = []

    async def generate(self, system, user, config=None):
        raise NotImplementedError

    async def generate_with_tools(self, messages, tools, config=None):
        self.seen.append(list(messages))
        if self.idx >= len(self.responses):
            return ToolCallResponse(content="done", model="mock")
        resp = self.responses[self.idx]
        self.idx += 1
        return resp

    async def generate_structured(self, system, user, response_model, config=None):
        raise NotImplementedError


class _FastChild(Agent):
    async def run(self) -> None:
        self.report(ReportPayload(
            task_id=self.task.id,
            summary=f"[fast-result from {self.task.description}]",
            files_written=["result.md"],
        ))


class _SlowChild(Agent):
    """Blocks until its description-keyed release Event is set (or cancelled).
    The events are controlled by the tests, so a sibling's lifetime is
    deterministic — no wall-clock sleep to race against."""

    release: dict[str, asyncio.Event] = {}

    async def run(self) -> None:
        key = self.task.description
        try:
            await _SlowChild.release.setdefault(key, asyncio.Event()).wait()
        except asyncio.CancelledError:
            if not self.last_report and not self.last_failure:
                self.fail("Agent cancelled")
            raise
        self.report(ReportPayload(
            task_id=self.task.id,
            summary=f"[slow-result from {key}]",
            files_written=["result.md"],
        ))


def _stream_runtime(tmp_path) -> Runtime:
    cfg = HarnessConfig(agent=AgentConfig(stream_children=True))
    return Runtime(
        artifact_root=tmp_path / "artifacts",
        repo_root=tmp_path / "repo",
        generated_root=tmp_path,
        config=cfg,
    )


@pytest.mark.asyncio
async def test_streaming_parent_acts_on_child_before_sibling_done(tmp_path) -> None:
    """Parent is re-admitted (and a child result injected) as the FAST child
    settles, even though the SLOW sibling is still running. An interim text-only
    turn while the sibling runs then WAITS for it instead of reporting (which
    would cancel the straggler)."""
    rt = _stream_runtime(tmp_path)
    rt.register_agent_class("FastChild", _FastChild)
    rt.register_agent_class("SlowChild", _SlowChild)
    # The slow sibling stays blocked until released; the releaser below lets it
    # settle once the parent is parked in its turn-2 wait.
    _SlowChild.release.clear()

    llm = _RecordingLLM([
        # Turn 1: delegate both children (fast + slow).
        ToolCallResponse(
            tool_calls=[
                ToolCallData(id="c1", name="delegate", arguments={"description": "fast task", "agent_type": "FastChild"}),
                ToolCallData(id="c2", name="delegate", arguments={"description": "slow task", "agent_type": "SlowChild"}),
            ],
            content=None, model="mock",
        ),
        # Turn 2: interim status prose while the slow sibling still runs —
        # a WAIT, not a final report.
        ToolCallResponse(
            tool_calls=None,
            content="Fast child settled. Still waiting for the slow one.", model="mock",
        ),
        # Turn 3: after the slow sibling settles, the final report.
        ToolCallResponse(tool_calls=None, content="all settled", model="mock"),
    ])
    rt.set_llm(llm)

    # Release the slow sibling deterministically once the parent makes its
    # second LLM call (the turn-2 wait), not on a wall-clock sleep.
    async def _release_on_parent_wait() -> None:
        while len(llm.seen) < 2:
            await asyncio.sleep(0.01)
        _SlowChild.release.setdefault("slow task", asyncio.Event()).set()

    releaser = asyncio.create_task(_release_on_parent_wait())
    try:
        root = rt.delegate(Task(description="orchestrate three delegated reads"))
        await root.run()
    finally:
        releaser.cancel()

    # Parent completed with a final report.
    assert root.task.status.value == "completed"
    assert root.last_report is not None

    # The parent's third LLM call must have seen the slow child's result...
    assert len(llm.seen) >= 3
    third_call_messages = llm.seen[2]
    joined = " ".join(str(m.get("content") or "") for m in third_call_messages)
    assert "child settled" in joined
    assert "slow-result" in joined

    # ...and no streamed child was cancelled: the interim text turn must NOT
    # have massacred the stragglers (a final report cancels them; a waiting
    # turn must not). The self-heal deliverable gate may resume/re-spawn
    # prose-only mock children, so assert on outcomes, not agent identity:
    # nothing anywhere may carry the "Agent cancelled" failure, and the slow
    # work must have finished with a report.
    failures = [
        a.last_failure.error or ""
        for a in rt.all_agents().values()
        if a.last_failure is not None
    ]
    assert not any("cancelled" in err for err in failures), failures
    slow_reports = [
        a for a in rt.all_agents().values()
        if isinstance(a, _SlowChild) and a.last_report is not None
    ]
    assert slow_reports


@pytest.mark.asyncio
async def test_empty_response_with_pending_children_waits(tmp_path) -> None:
    """An empty provider response while streamed children are still running is
    a nothing-turn: the parent waits for the children instead of failing.
    fail() also cancels stream children, so failing here would be the same
    massacre as the interim-report one, via a different door."""
    rt = _stream_runtime(tmp_path)
    rt.register_agent_class("SlowChild", _SlowChild)
    _SlowChild.release.clear()

    llm = _RecordingLLM([
        # Turn 1: delegate two slow children. The first settles during this
        # turn's harvest (released below, before the run starts); the second
        # stays pending into turn 2.
        ToolCallResponse(
            tool_calls=[
                ToolCallData(id="c1", name="delegate", arguments={"description": "slow a", "agent_type": "SlowChild"}),
                ToolCallData(id="c2", name="delegate", arguments={"description": "slow b", "agent_type": "SlowChild"}),
            ],
            content=None, model="mock",
        ),
        # Turn 2: degenerate empty response while "slow b" still runs — must
        # WAIT, not fail (fail() cancels stream children).
        ToolCallResponse(tool_calls=None, content=None, model="mock"),
        # Turn 3: after the second child settles, the final report.
        ToolCallResponse(tool_calls=None, content="done", model="mock"),
    ])
    rt.set_llm(llm)

    # Stage the releases on observable facts, not wall-clock sleeps: "slow a"
    # is released up front, so it settles during turn 1's harvest (which is
    # what lets turn 2 happen at all); "slow b" is released once the parent
    # makes its second LLM call — the empty turn-2 wait.
    _SlowChild.release.setdefault("slow a", asyncio.Event()).set()

    async def _release_second_on_parent_wait() -> None:
        while len(llm.seen) < 2:
            await asyncio.sleep(0.01)
        _SlowChild.release.setdefault("slow b", asyncio.Event()).set()

    releaser = asyncio.create_task(_release_second_on_parent_wait())
    try:
        root = rt.delegate(Task(description="orchestrate"))
        await root.run()
    finally:
        releaser.cancel()

    assert root.task.status.value == "completed"
    assert root.last_report is not None
    assert len(llm.seen) == 3

    # The slow child finished with a report instead of being cancelled: the
    # empty parent turn must not have routed to fail() (which cancels stream
    # children). Outcome-based, not identity-based (see the deliverable-gate
    # note in the interim-text test above).
    failures = [
        a.last_failure.error or ""
        for a in rt.all_agents().values()
        if a.last_failure is not None
    ]
    assert not any("cancelled" in err for err in failures), failures
    assert any(
        isinstance(a, _SlowChild) and a.last_report is not None
        for a in rt.all_agents().values()
    )


@pytest.mark.asyncio
async def test_default_non_streaming_blocks_until_all_children_done(tmp_path) -> None:
    """With stream_children=False (the default), the parent must wait for BOTH
    children and cannot act between them — the gather path surfaces results only
    after all siblings settle."""
    rt = Runtime(
        artifact_root=tmp_path / "artifacts", repo_root=tmp_path / "repo",
        generated_root=tmp_path,
        config=HarnessConfig(agent=AgentConfig(stream_children=False)),
    )
    rt.register_agent_class("FastChild", _FastChild)
    rt.register_agent_class("SlowChild", _SlowChild)
    # Both children must settle for the gather to surface their results.
    _SlowChild.release.setdefault("slow task", asyncio.Event()).set()

    llm = _RecordingLLM([
        ToolCallResponse(
            tool_calls=[
                ToolCallData(id="c1", name="delegate", arguments={"description": "fast task", "agent_type": "FastChild"}),
                ToolCallData(id="c2", name="delegate", arguments={"description": "slow task", "agent_type": "SlowChild"}),
            ],
            content=None, model="mock",
        ),
        ToolCallResponse(tool_calls=None, content="all settled", model="mock"),
    ])
    rt.set_llm(llm)

    root = rt.delegate(Task(description="orchestrate"))
    await root.run()

    assert root.task.status.value == "completed"
    # Only ONE structural turn: the gather produced both results together; the
    # second LLM call saw both children (no per-child "child settled" event).
    assert len(llm.seen) == 2
    joined = " ".join(str(m.get("content") or "") for m in llm.seen[1])
    assert "fast-result" in joined and "slow-result" in joined