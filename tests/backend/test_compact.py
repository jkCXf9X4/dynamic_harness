from __future__ import annotations

import pytest

from dynamic_harness.core.agent import Agent
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import ActivityEventType, Task, TaskStatus
from dynamic_harness.llm.provider import LLMProvider, ToolCallData, ToolCallResponse


class _CompactLLM(LLMProvider):
    """Deterministic LLM for the operator-driven compaction tests.

    Call #1 returns a `status` tool call and, as a side effect, queues an
    operator compaction request (as the CLI `/compact` command would). Call #2
    is the compression summarization produced by that request (returns the
    summary text). Every later call returns plain content that completes the
    run. `_calls_1_before_run` lets a test pre-set the flag so the compaction
    happens on the very first loop iteration instead.
    """

    def __init__(self, agent: Agent) -> None:
        self.agent = agent
        self.calls = 0

    async def generate(self, system: str, user: str, config=None):
        raise NotImplementedError

    async def generate_with_tools(self, messages, tools, config=None):
        self.calls += 1
        if self.calls == 1:
            self.agent.request_compaction()  # operator asks for compaction mid-run
            return ToolCallResponse(
                tool_calls=[ToolCallData(id="c1", name="status", arguments={})],
                content=None, model="mock",
            )
        if self.calls == 2:
            return ToolCallResponse(content="COMPACTED-SUMMARY", model="mock")
        return ToolCallResponse(content="all done", model="mock")

    async def generate_structured(self, system, user, response_model, config=None):
        raise NotImplementedError


def _make_agent(runtime: Runtime, description: str = "test") -> Agent:
    task = Task(description=description)
    task.status = TaskStatus.running
    agent = Agent("test-agent", task, runtime)
    runtime._agents[agent.id] = agent
    return agent


def _set_llm(runtime: Runtime, agent: Agent, llm: LLMProvider) -> None:
    """Wire an LLM for this agent.

    ``Agent.__init__`` pins ``self._llm`` from ``runtime.provider`` at
    construction time, so a provider injected afterwards must also be pushed
    onto the agent itself (tests reach into the private seam, as elsewhere).
    """
    runtime.set_llm(llm)
    agent._llm = llm


# ── Operator request_compaction → run loop ─────────────────────────────

@pytest.mark.asyncio
async def test_request_compaction_during_run_compresses_context(runtime: Runtime) -> None:
    agent = _make_agent(runtime)
    _set_llm(runtime, agent, _CompactLLM(agent))

    events: list[str] = []
    runtime.on_activity(lambda e: events.append(e.event_type.value))

    await agent.run()

    assert agent.task.status.value == "completed"
    assert agent.last_report is not None
    assert agent.last_report.summary == "all done"
    # The compaction ran at the loop's safe point: history was replaced by the
    # LLM summary, so the final context is just system + compressed summary.
    assert [m.get("role") for m in agent.context.messages] == ["system", "system"]
    assert any(
        str(m.get("content", "")).startswith("[Context compressed] COMPACTED-SUMMARY")
        for m in agent.context.messages
    )
    # The standard COMPRESSION activity event was emitted for actors/gauge.
    assert ActivityEventType.COMPRESSION.value in events


@pytest.mark.asyncio
async def test_request_compaction_flag_and_small_context_noop(runtime: Runtime) -> None:
    agent = _make_agent(runtime)
    _set_llm(runtime, agent, _CompactLLM(agent))

    assert not agent._compact_event.is_set()
    agent.request_compaction()
    assert agent._compact_event.is_set()

    # With a context too small to compress (< 3 messages), _apply_compaction
    # is a silent no-op and does not call the LLM. (Clearing the flag is the
    # run loop's job, so it stays set for the loop to consume later.)
    await agent._apply_compaction()
    assert agent._compact_event.is_set() is True
    assert _llm(agent).calls == 0  # compression never reached the provider
    assert not any(
        str(m.get("content", "")).startswith("[Context compressed]")
        for m in agent.context.messages
    )


# ── CLI /compact dispatch ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_compact_command_on_active_root_queues_compaction(runtime: Runtime) -> None:
    from dynamic_harness.cli.terminal import _run_command

    agent = runtime.delegate(Task(description="top task"))
    runtime._active_root = agent  # delegate doesn't set it; run() does

    # `/compact` must work while a run is active: _submit_input dispatches
    # mid-run lines with allow_run_commands=False (which blocks /resume//reset).
    handled = await _run_command(runtime, "/compact", allow_run_commands=False)

    assert handled is True
    assert agent._compact_event.is_set()


@pytest.mark.asyncio
async def test_compact_command_on_terminal_root_queues_for_continuation(runtime: Runtime) -> None:
    from dynamic_harness.cli.terminal import _run_command

    agent = runtime.delegate(Task(description="top task"))
    agent.task.status = TaskStatus.completed
    runtime._active_root = agent

    handled = await _run_command(runtime, "/compact")

    # Even a finished root gets the request: the interactive terminal reuses
    # the root across continuations, so the flag is honored on the next run.
    assert handled is True
    assert agent._compact_event.is_set()


@pytest.mark.asyncio
async def test_compact_command_without_active_root_is_safe(runtime: Runtime) -> None:
    from dynamic_harness.cli.terminal import _run_command

    assert runtime.active_root() is None
    handled = await _run_command(runtime, "/compact")
    assert handled is True


def _llm(agent: Agent) -> _CompactLLM:
    assert isinstance(agent._llm, _CompactLLM)
    return agent._llm