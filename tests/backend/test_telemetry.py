from __future__ import annotations

import asyncio

from dynamic_harness.core.agent import Agent
from dynamic_harness.core.events_format import format_event
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import ActivityEvent, ActivityEventType, Task
from dynamic_harness.llm.provider import LLMProvider, ToolCallData, ToolCallResponse


class _ScriptedLLM(LLMProvider):
    """Returns a scripted response sequence; falls back to a plain text reply."""

    def __init__(self, responses: list[ToolCallResponse]) -> None:
        self.responses = responses
        self.idx = 0

    async def generate(self, system, user, config=None):
        raise NotImplementedError

    async def generate_with_tools(self, messages, tools, config=None):
        resp = self.responses[self.idx] if self.idx < len(self.responses) else None
        self.idx += 1
        if resp is None:
            return ToolCallResponse(content="done", model="mock")
        return resp

    async def generate_structured(self, system, user, response_model, config=None):
        raise NotImplementedError


def _runtime(tmp_path) -> Runtime:
    return Runtime(
        artifact_root=tmp_path / "artifacts",
        repo_root=tmp_path / "repo",
        generated_root=tmp_path,
    )


async def _replies(runtime: Runtime, agent: Agent) -> list[ActivityEvent]:
    events: list[ActivityEvent] = []
    runtime.on_activity(
        lambda e: events.append(e)
        if e.event_type == ActivityEventType.ASSISTANT_REPLY
        else None
    )
    await asyncio.wait_for(agent.run(), timeout=5)
    return events


async def test_assistant_reply_emitted_for_text_turns(tmp_path) -> None:
    """Every completed LLM call carrying text emits one assistant_reply event
    carrying exactly that content, attributed to the agent that called."""
    rt = _runtime(tmp_path)
    rt.set_llm(_ScriptedLLM([
        ToolCallResponse(tool_calls=None, content="First reply", model="mock"),
    ]))
    root = rt.delegate(Task(description="reply"))
    events = await _replies(rt, root)

    assert [e.data["content"] for e in events] == ["First reply"]
    assert all(e.agent_id == root.id for e in events)
    assert all(e.event_type == ActivityEventType.ASSISTANT_REPLY for e in events)


async def test_assistant_reply_skipped_when_content_blank(tmp_path) -> None:
    """Pure tool-call turns (no text) must not emit assistant_reply events."""
    rt = _runtime(tmp_path)
    rt.set_llm(_ScriptedLLM([
        ToolCallResponse(
            tool_calls=[ToolCallData(id="c1", name="read", arguments={"path": "/x.txt"})],
            content=None, model="mock",
        ),
    ]))
    root = rt.delegate(Task(description="read a file"))
    events = await _replies(rt, root)

    assert [e.data["content"] for e in events] == [
        "done"  # only the fallback text turn; the tool-only turn stayed silent
    ]


def test_format_event_assistant_reply_collapses_newlines():
    event = ActivityEvent(
        agent_id="a" * 12,
        event_type=ActivityEventType.ASSISTANT_REPLY,
        data={"content": "hello\nworld"},
    )
    line = format_event(event)
    assert line == "  [aaaaaaaa] hello world"