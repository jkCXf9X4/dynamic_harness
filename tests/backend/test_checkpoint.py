from __future__ import annotations

from pathlib import Path

import pytest

from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import Task
from dynamic_harness.llm.provider import (
    LLMProvider,
    LLMResponse,
    ToolCallData,
    ToolCallResponse,
)


class ScriptedProvider(LLMProvider):
    """Deterministic LLM that replays a fixed list of responses."""

    default_model = "test-model"

    def __init__(self, responses: list[ToolCallResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[list[dict]] = []
        self.usage = {"prompt_tokens": 5, "completion_tokens": 5, "cached_tokens": 0}

    async def generate(self, system: str, user: str, config=None) -> LLMResponse:
        raise NotImplementedError

    async def generate_structured(self, system, user, response_model, config=None) -> object:
        raise NotImplementedError

    async def generate_with_tools(self, messages: list[dict], tools: list[dict], config=None):
        self.calls.append(list(messages))
        if not self.responses:
            return ToolCallResponse(content="done", model=self.default_model, usage=self.usage)
        return self.responses.pop(0)

    async def aclose(self) -> None:
        pass


def _tool(cid: str, name: str, args: dict) -> ToolCallResponse:
    return ToolCallResponse(
        content=None,
        tool_calls=[ToolCallData(id=cid, name=name, arguments=args)],
        model="m",
        usage={"prompt_tokens": 5, "completion_tokens": 3, "cached_tokens": 0},
    )


def _done(content: str = "done") -> ToolCallResponse:
    return ToolCallResponse(content=content, tool_calls=None, model="m", usage=None)


def _make_runtime(tmp: Path, ckpt: Path) -> Runtime:
    return Runtime(
        artifact_root=tmp / "artifacts",
        repo_root=tmp / "repo",
        generated_root=tmp,
        checkpoint_root=ckpt,
    )


@pytest.mark.asyncio
async def test_checkpoint_roundtrip_preserves_plan_and_turns(tmp: Path) -> None:
    rt = _make_runtime(tmp / "rt", tmp / "ckpt")
    agent = rt.delegate(Task(description="build a thing"))
    agent.set_plan(
        steps=["analyze", "write code"],
        objective="ship a working module",
        acceptance=["compiles", "tested"],
        deliverable="a .py module",
    )
    assistant = {
        "role": "assistant",
        "content": "starting",
        "tool_calls": [{"id": "c0", "type": "function", "function": {"name": "write", "arguments": "{}"}}],
    }
    results = [{"role": "tool", "tool_call_id": "c0", "content": "wrote file"}]
    agent.context.commit_turn(assistant, results)
    agent.persist_checkpoint()

    cp = rt.checkpoint_store.load(agent.id)
    assert cp is not None
    assert cp.focus.get("objective") == "ship a working module"
    assert "analyze" in cp.focus.get("pending", [])
    assert cp.focus.get("acceptance") == ["compiles", "tested"]
    assert len(cp.messages) >= 2
    assert cp.turn_counter == 1
    assert cp.turn_order == ["t0"]
    assert cp.task.id == agent.task.id


@pytest.mark.asyncio
async def test_auto_and_explicit_checkpoint_persist_notes(tmp: Path) -> None:
    rt = _make_runtime(tmp / "rt", tmp / "ckpt")
    out = tmp / "rt" / "out.txt"
    rt.set_llm(ScriptedProvider([
        _tool("c0", "plan", {"steps": ["analyze", "write"]}),
        _tool("c1", "checkpoint", {"note": "first milestone done"}),
        _tool("c2", "write", {"path": str(out), "content": "data"}),
        _tool("c3", "fail", {"error": "simulated abort"}),
    ]))

    root = rt.delegate(Task(description="build out.txt"))
    await root.run()

    assert root.last_failure is not None
    assert "simulated abort" in root.last_failure.error
    assert out.exists() and out.read_text() == "data"
    cp = rt.checkpoint_store.load(root.id)
    assert cp is not None
    assert "analyze" in cp.focus.get("pending", [])
    assert "first milestone done" in cp.checkpoint_notes
    assert cp.terminated is True


@pytest.mark.asyncio
async def test_resume_aborted_task_from_fresh_runtime(tmp: Path) -> None:
    ckpt = tmp / "ckpt"
    rt1 = _make_runtime(tmp / "rt1", ckpt)
    out = tmp / "rt1" / "out.txt"
    rt1.set_llm(ScriptedProvider([
        _tool("c0", "plan", {"steps": ["gather", "finalize"]}),
        _tool("c1", "write", {"path": str(out), "content": "data"}),
        _tool("c2", "fail", {"error": "aborted"}),
    ]))

    root = rt1.delegate(Task(description="build a file on disk"))
    await root.run()
    agent_id = root.id
    assert root.last_failure is not None
    assert (ckpt / f"{agent_id}.json").exists()

    # A fresh process sharing the checkpoint dir: rebuild the agent from disk
    # and drive it to a successful report (no work is lost).
    rt2 = _make_runtime(tmp / "rt2", ckpt)
    rt2.set_llm(ScriptedProvider([_tool("cx", "report", {"summary": "resumed and done"})]))
    recovered = await rt2.resume(agent_id)

    assert recovered.task.status.value == "completed"
    assert recovered.last_report is not None
    assert "resumed and done" in recovered.last_report.summary
    assert out.exists()
    assert "gather" in (recovered.focus.pending or [])


@pytest.mark.asyncio
async def test_checkpoint_dir_removed_midrun_is_nonfatal_and_self_heals(tmp: Path) -> None:
    """Deleting the checkpoints dir mid-run mimics the trace.jsonl failure: a
    FileNotFoundError from the checkpoint write must NEVER fail the run (even a
    top agent) — it self-heals by recreating the dir and keeps working."""
    ckpt = tmp / "ckpt"
    rt = _make_runtime(tmp / "rt", ckpt)
    out = tmp / "rt" / "out.txt"
    rt.set_llm(ScriptedProvider([
        _tool("c0", "write", {"path": str(out), "content": "phase1"}),
        _tool("c1", "write", {"path": str(out), "content": "phase2"}),
        _tool("c2", "report", {"summary": "ran to completion"}),
    ]))

    # Simulate a session/workdir cleanup between the construct and the run.
    rt.checkpoint_store.clear()
    import shutil as _shutil
    _shutil.rmtree(ckpt, ignore_errors=True)

    root = rt.delegate(Task(description="build a file on disk"))
    await root.run()

    assert root.last_report is not None
    assert "ran to completion" in root.last_report.summary
    assert out.read_text() == "phase2"
    # The store self-healed the removed dir and persisted the final state.
    assert ckpt.exists()
    assert (ckpt / f"{root.id}.json").exists()