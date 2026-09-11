from __future__ import annotations

import asyncio

from dynamic_harness.core.agent import Agent
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import ReportPayload, Task
from dynamic_harness.llm.provider import LLMProvider, ToolCallData, ToolCallResponse


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
        resp = self.responses[self.idx] if self.idx < len(self.responses) else None
        self.idx += 1
        if resp is None:
            return ToolCallResponse(content="done", model="mock")
        return resp

    async def generate_structured(self, system, user, response_model, config=None):
        raise NotImplementedError


class _SlowChild(Agent):
    def __init__(self, *args, delay: float = 0.5, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.delay = delay

    async def run(self) -> None:
        try:
            await asyncio.sleep(self.delay)
        except asyncio.CancelledError:
            if not self.last_report and not self.last_failure:
                self.fail("Agent cancelled")
            raise
        self.report(ReportPayload(
            task_id=self.task.id, summary="claim-123-verified",
        ))


class _ToolLLM(LLMProvider):
    """Two iterations per turn: one read tool-call, then a report."""

    def __init__(self) -> None:
        self.turn = 0

    async def generate(self, system, user, config=None):
        raise NotImplementedError

    async def generate_with_tools(self, messages, tools, config=None):
        self.turn += 1
        if self.turn % 2 == 1:
            return ToolCallResponse(
                tool_calls=[ToolCallData(id=f"c{self.turn}", name="read", arguments={"path": "/x.txt"})],
                content=None, model="mock",
            )
        return ToolCallResponse(
            tool_calls=None, content=f"answer turn {self.turn}", model="mock",
        )

    async def generate_structured(self, system, user, response_model, config=None):
        raise NotImplementedError


def _runtime(tmp_path) -> Runtime:
    rt = Runtime(
        artifact_root=tmp_path / "artifacts", repo_root=tmp_path / "repo",
        generated_root=tmp_path,
    )
    rt.register_agent_class("SlowChild", _SlowChild)
    return rt


async def test_midrun_input_answers_while_child_executes(tmp_path) -> None:
    """Typing during a child-wait lets the top agent answer immediately: its next
    LLM call must include the user's message as a fresh user turn (FR-3.5.3)."""
    rt = _runtime(tmp_path)
    llm = _RecordingLLM([
        ToolCallResponse(
            tool_calls=[ToolCallData(id="c1", name="delegate", arguments={
                "description": "verify claim 123",
                "agent_type": "SlowChild",
            })],
            content=None, model="mock",
        ),
        ToolCallResponse(
            tool_calls=None, content="Here is my direct answer", model="mock",
        ),
    ])
    rt.set_llm(llm)

    root = rt.delegate(Task(description="verify claims"))
    run_task = asyncio.create_task(root.run())

    await asyncio.sleep(0.15)  # let the parent reach the child-gather
    root.submit_input("ANSWER ME DIRECTLY while the subtask runs")
    await asyncio.wait_for(run_task, timeout=5)

    assert root.task.status.value == "completed"
    assert root.last_report is not None
    assert root.last_report.summary == "Here is my direct answer"
    assert len(llm.seen) >= 2
    second = " ".join(str(m.get("content") or "") for m in llm.seen[1])
    assert "ANSWER ME DIRECTLY" in second


async def test_interrupted_gather_keeps_children_non_lossy(tmp_path) -> None:
    """When the parent reacts to mid-run input and KEEPS WORKING (tool call, not
    report), the interrupted child-wait is re-entered and the child's result
    still folds into the parent's context under the ``[child settled]``
    convention. The delegation must not be lost by the interruption."""
    rt = _runtime(tmp_path)
    llm = _RecordingLLM([
        ToolCallResponse(
            tool_calls=[ToolCallData(id="c1", name="delegate", arguments={
                "description": "verify claim 123",
                "agent_type": "SlowChild",
            })],
            content=None, model="mock",
        ),
        ToolCallResponse(
            tool_calls=[ToolCallData(id="c2", name="read", arguments={"path": "/x.txt"})],
            content=None, model="mock",
        ),
        ToolCallResponse(
            tool_calls=None, content="Synthesis with child evidence ready.", model="mock",
        ),
    ])
    rt.set_llm(llm)

    root = rt.delegate(Task(description="verify claims"))
    run_task = asyncio.create_task(root.run())

    await asyncio.sleep(0.1)  # parent is blocked in the child-gather
    root.submit_input("status?")
    await asyncio.wait_for(run_task, timeout=5)

    assert root.task.status.value == "completed"
    # The parent's third call saw the child's result folded in — the delegation
    # survived the mid-run interruption.
    assert len(llm.seen) >= 3
    third = " ".join(str(m.get("content") or "") for m in llm.seen[2])
    assert "claim-123-verified" in third


async def test_continue_with_input_resets_iteration_state(tmp_path) -> None:
    """Each interactive continuation is a fresh turn: per-run safety state must
    not accumulate across REPL messages (a long session must not trip
    max_iterations prematurely)."""
    rt = Runtime(
        artifact_root=tmp_path / "artifacts", repo_root=tmp_path / "repo",
        generated_root=tmp_path,
    )
    rt.set_llm(_ToolLLM())  # 2 iterations per turn → needs a budget of 3 to trip

    task = Task(description="first task")
    root = rt.delegate(task)
    root.safety_max_iterations = 3

    for i in range(4):
        await rt.run(f"message {i}", root_agent=root)
        assert root.task.status.value == "completed", (
            f"turn {i} force-failed: {root.last_failure}"
        )
        assert root._iteration <= 2  # per-turn budget, not cumulative