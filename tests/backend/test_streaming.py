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
        ))


class _SlowChild(Agent):
    async def run(self) -> None:
        try:
            await asyncio.sleep(5.0)
        except asyncio.CancelledError:
            if not self.last_report and not self.last_failure:
                self.fail("Agent cancelled")
            raise
        self.report(ReportPayload(
            task_id=self.task.id,
            summary=f"[slow-result from {self.task.description}]",
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
    settles, even though the SLOW sibling is still running. Cancelling the
    sibling on report leaves it failed."""
    rt = _stream_runtime(tmp_path)
    rt.register_agent_class("FastChild", _FastChild)
    rt.register_agent_class("SlowChild", _SlowChild)

    llm = _RecordingLLM([
        # Turn 1: delegate both children (fast + slow).
        ToolCallResponse(
            tool_calls=[
                ToolCallData(id="c1", name="delegate", arguments={"description": "fast task", "agent_type": "FastChild"}),
                ToolCallData(id="c2", name="delegate", arguments={"description": "slow task", "agent_type": "SlowChild"}),
            ],
            content=None, model="mock",
        ),
        # Turn 2: the parent is asked again AFTER the fast child settles but
        # BEFORE the slow one completes; it reports (which cancels the slow
        # straggler).
        ToolCallResponse(
            tool_calls=None,
            content="Fast child settled. Reporting now while slow still runs.", model="mock",
        ),
    ])
    rt.set_llm(llm)

    root = rt.delegate(Task(description="orchestrate three delegated reads"))
    await root.run()

    # Parent completed.
    assert root.task.status.value == "completed"
    assert root.last_report is not None

    # The parent's second LLM call must have seen the fast child's result...
    assert len(llm.seen) >= 2
    second_call_messages = llm.seen[1]
    joined = " ".join(str(m.get("content") or "") for m in second_call_messages)
    assert "child settled" in joined
    assert "fast-result" in joined

    # ...but NOT the slow child's result (it was still running when parent reported).
    assert "slow-result" not in joined

    # The slow child was a straggler: cancelled, never reported.
    await asyncio.sleep(0.05)  # let cancellation propagate to the child
    slow = rt.get_agent(
        next(aid for aid, a in rt.all_agents().items() if a.task.description == "slow task")
    )
    assert slow.last_report is None
    assert slow.task.status.value == "failed"


@pytest.mark.asyncio
async def test_default_non_streaming_blocks_until_all_children_done(tmp_path) -> None:
    """With stream_children=False (the default), the parent must wait for BOTH
    children and cannot act between them — the gather path surfaces results only
    after all siblings settle."""
    rt = Runtime(
        artifact_root=tmp_path / "artifacts", repo_root=tmp_path / "repo",
        generated_root=tmp_path,
    )
    rt.register_agent_class("FastChild", _FastChild)
    rt.register_agent_class("SlowChild", _SlowChild)

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