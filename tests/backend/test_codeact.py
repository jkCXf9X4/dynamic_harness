from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pytest

from dynamic_harness.config import HarnessConfig, InvokeConfig
from dynamic_harness.core.agent import Agent
from dynamic_harness.core.codeact import CODECT_TOOLS, CodeActAgent
from dynamic_harness.core.policies.loop_guard import invoke_family
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import ReportPayload, Task
from dynamic_harness.llm.provider import LLMProvider, ToolCallData, ToolCallResponse


# ── scripted mock LLM (same shape as the other agent-loop tests) ──────────

class _ScriptedLLM(LLMProvider):
    def __init__(self, responses: list[ToolCallResponse]) -> None:
        self.responses = responses
        self.idx = 0
        self.seen_tools: list[list[dict]] = []

    async def generate(self, system, user, config=None):
        raise NotImplementedError

    async def generate_with_tools(self, messages, tools, config=None):
        self.seen_tools.append(list(tools))
        if self.idx >= len(self.responses):
            return ToolCallResponse(content="done", model="mock")
        resp = self.responses[self.idx]
        self.idx += 1
        return resp

    async def generate_structured(self, system, user, response_model, config=None):
        raise NotImplementedError


class _FastChild(Agent):
    """No-LLM child that reports immediately — for the delegate-through-bridge test."""

    async def run(self) -> None:
        self.report(ReportPayload(task_id=self.task.id, summary=f"[fast:{self.task.description}]"))


def _invoke_rt(tmp_path: Path, **invoke_kwargs) -> Runtime:
    config = HarnessConfig(invoke=InvokeConfig(**invoke_kwargs)) if invoke_kwargs else None
    return Runtime(
        artifact_root=tmp_path / "artifacts", repo_root=tmp_path / "repo",
        generated_root=tmp_path, config=config,
    )


# ── tool-level tests (no LLM needed) ─────────────────────────────────────

@pytest.mark.asyncio
async def test_invoke_runs_code_and_returns_stdout(tmp_path: Path) -> None:
    rt = _invoke_rt(tmp_path)
    agent = rt.delegate(Task(description="probe"))
    result = await rt.tool_registry.execute(
        "invoke", "tc1", agent=agent, code="print(sum(i * i for i in range(10)))"
    )
    assert result.content.strip() == "285"


@pytest.mark.asyncio
async def test_invoke_rpc_read_full_content_and_footer(tmp_path: Path) -> None:
    rt = _invoke_rt(tmp_path)
    agent = rt.delegate(Task(description="probe"))
    (tmp_path / "sample.txt").write_text("hello harness\nsecond line\n")
    result = await rt.tool_registry.execute(
        "invoke", "tc2", agent=agent,
        code=(
            "from harness_tools import read\n"
            "t = read('sample.txt')\n"
            "print('line1:', t.splitlines()[0])\n"
        ),
    )
    assert "line1: hello harness" in result.content
    # The snapshot handle is advertised so the model can page it.
    assert re.search(r"# result: [0-9a-f]{12}", result.content)


@pytest.mark.asyncio
async def test_invoke_rpc_write_glob_plan_usage(tmp_path: Path) -> None:
    rt = _invoke_rt(tmp_path)
    agent = rt.delegate(Task(description="probe"))
    result = await rt.tool_registry.execute(
        "invoke", "tc3", agent=agent,
        code=(
            "from harness_tools import write, glob, plan, usage\n"
            "write('made.txt', 'x')\n"
            "print('made:', 'made.txt' in glob('*.txt'))\n"
            "print(plan(['a', 'b'], objective='o'))\n"
            "print('usage-ok:', 'agent_id' in usage())\n"
        ),
    )
    assert "made: True" in result.content
    assert "Plan recorded: 2 pending step(s)" in result.content
    assert "usage-ok: True" in result.content
    assert (tmp_path / "made.txt").exists()


@pytest.mark.asyncio
async def test_invoke_terminal_marker_report_completes_agent(tmp_path: Path) -> None:
    rt = _invoke_rt(tmp_path)
    agent = rt.delegate(Task(description="probe"))
    result = await rt.tool_registry.execute(
        "invoke", "tc4", agent=agent,
        code=(
            "from harness_tools import report\n"
            "print(report('probe finished', confidence=0.9))\n"
        ),
    )
    assert "[terminal: report delivered]" in result.content
    assert agent.task.status.value == "completed"
    assert agent.last_report is not None
    assert agent.last_report.summary == "probe finished"
    assert agent.last_report.confidence == 0.9


@pytest.mark.asyncio
async def test_invoke_terminal_marker_fail_fails_agent(tmp_path: Path) -> None:
    rt = _invoke_rt(tmp_path)
    agent = rt.delegate(Task(description="probe"))
    result = await rt.tool_registry.execute(
        "invoke", "tc5", agent=agent,
        code=(
            "from harness_tools import fail\n"
            "print(fail('blocked: no API key'))\n"
        ),
    )
    assert "[terminal: failed]" in result.content
    assert agent.task.status.value == "failed"
    assert agent.last_failure is not None
    assert "no API key" in agent.last_failure.error


@pytest.mark.asyncio
async def test_invoke_rpc_never_reaches_terminal_tools_directly(tmp_path: Path) -> None:
    """The bridge refuses terminal tools as RPC names (markers are the channel),
    and recursive invoke / bash are not on the stub surface at all."""
    rt = _invoke_rt(tmp_path)
    agent = rt.delegate(Task(description="probe"))
    result = await rt.tool_registry.execute(
        "invoke", "tc6", agent=agent,
        code=(
            "from harness_tools import _call\n"
            "print(_call('report', summary='hax'))\n"
        ),
    )
    assert "not available inside invoke" in result.content
    assert "# TERMINAL:report:" not in result.content


@pytest.mark.asyncio
async def test_invoke_timeout_kills_process_group(tmp_path: Path) -> None:
    rt = _invoke_rt(tmp_path)
    agent = rt.delegate(Task(description="probe"))
    result = await rt.tool_registry.execute(
        "invoke", "tc7", agent=agent,
        code="import time\nprint('start')\ntime.sleep(30)\nprint('never')\n",
        timeout=1200,
    )
    assert "timed out after 1200ms" in result.content
    assert "process group was killed" in result.content


@pytest.mark.asyncio
async def test_invoke_import_allowlist_refuses(tmp_path: Path) -> None:
    rt = _invoke_rt(tmp_path, import_allowlist=["json", "os"])
    agent = rt.delegate(Task(description="probe"))
    result = await rt.tool_registry.execute(
        "invoke", "tc8", agent=agent, code="import requests\nprint('x')\n"
    )
    assert "invoke refused" in result.content
    assert "requests" in result.content
    # Allowlisted import is fine.
    result2 = await rt.tool_registry.execute(
        "invoke", "tc9", agent=agent, code="import json\nprint(json.dumps({'ok': 1}))\n"
    )
    assert "invoke refused" not in result2.content


@pytest.mark.asyncio
async def test_invoke_rpc_delegate_runs_child_through_bridge(tmp_path: Path) -> None:
    """With streaming off, a bridge ``delegate`` runs its child synchronously and
    the sandboxed code sees the settled child's formatted result (policy parity:
    the default streaming mode returns 'running' fire-and-forget instead)."""
    from dynamic_harness.config import AgentConfig, HarnessConfig

    rt = Runtime(
        artifact_root=tmp_path / "artifacts", repo_root=tmp_path / "repo",
        generated_root=tmp_path,
        config=HarnessConfig(agent=AgentConfig(stream_children=False)),
    )
    rt.register_agent_class("fast", _FastChild)
    agent = rt.delegate(Task(description="probe"))
    result = await rt.tool_registry.execute(
        "invoke", "tc10", agent=agent,
        code=(
            "from harness_tools import delegate\n"
            "import json\n"
            "out = delegate('child job', agent_type='fast')\n"
            "d = json.loads(out)\n"
            "print('child:', d.get('status'), d.get('summary'))\n"
        ),
    )
    assert "child: completed" in result.content


# ── codeact agent type ───────────────────────────────────────────────────

def test_register_codeact(tmp_path: Path) -> None:
    rt = _invoke_rt(tmp_path)
    rt.register_agent_class("codeact", CodeActAgent)
    assert rt.has_agent_class("codeact")
    assert "codeact" in rt.registered_agent_classes()


@pytest.mark.asyncio
async def test_codeact_agent_runs_invoke_to_terminal(tmp_path: Path) -> None:
    """End-to-end: the codeact agent's ONLY action tool is invoke; a snippet
    that prints a report marker completes the run with the reported summary."""
    llm = _ScriptedLLM([
        ToolCallResponse(tool_calls=[
            ToolCallData(
                id="c1", name="invoke",
                arguments={"code": (
                    "from harness_tools import report\n"
                    "print(report('codeact done', confidence=0.8))\n"
                )},
            ),
        ]),
    ])
    rt = _invoke_rt(tmp_path)
    rt.register_agent_class("codeact", CodeActAgent)
    rt.set_llm(llm)
    task = Task(description="do the thing")
    agent = rt.delegate(task, agent_type="codeact")
    await agent.run()
    assert agent.task.status.value == "completed"
    assert agent.last_report is not None
    assert agent.last_report.summary == "codeact done"


@pytest.mark.asyncio
async def test_codeact_exposed_surface_is_minimal(tmp_path: Path) -> None:
    """The model only ever sees the minimalist toolset (proposal §5)."""
    llm = _ScriptedLLM([
        ToolCallResponse(tool_calls=[
            ToolCallData(
                id="c1", name="invoke",
                arguments={"code": "print('hi')\n"},
            ),
        ]),
        ToolCallResponse(content="done", tool_calls=None, model="mock"),
    ])
    rt = _invoke_rt(tmp_path)
    rt.register_agent_class("codeact", CodeActAgent)
    rt.set_llm(llm)
    agent = rt.delegate(Task(description="probe"), agent_type="codeact")
    await agent.run()
    assert llm.seen_tools, "the agent must have called the LLM"
    names = {t["function"]["name"] for t in llm.seen_tools[0]}
    assert names == set(CODECT_TOOLS)
    assert "bash" not in names and "delegate" not in names and "read" not in names


@pytest.mark.asyncio
async def test_default_agent_still_has_full_surface_with_invoke(tmp_path: Path) -> None:
    """The hybrid: default agents keep the rich surface PLUS the invoke tool."""
    rt = _invoke_rt(tmp_path)
    rt.set_llm(_ScriptedLLM([ToolCallResponse(content="done", model="mock")]))
    agent = rt.delegate(Task(description="probe"))
    await agent.run()
    assert "invoke" in rt.tool_registry.list_tools()
    assert "delegate" in rt.tool_registry.list_tools()


# ── loop-guard source-normalized family ──────────────────────────────────

def test_invoke_family_normalizes_comments_and_whitespace() -> None:
    a = "def f():\n    # a comment\n    return sorted(x)\nprint(f())\n"
    b = "def f():\n    return sorted(x)\n\n\nprint(f())\n"
    assert invoke_family(a) == invoke_family(b)
    assert invoke_family("print('different logic')") != invoke_family(a)


@pytest.mark.asyncio
async def test_codeact_agent_uses_invoke_family_for_near_identical(tmp_path: Path) -> None:
    from dynamic_harness.core.policies.loop_guard import LoopGuard

    guard = LoopGuard(
        near_identical_threshold=2,
        near_identical_window=4,
        near_identical_similarity=0.5,
        near_identical_tools=("invoke",),
        near_identical_warning_attempts=1,
    )

    class _TC:
        def __init__(self, name: str, arguments: dict) -> None:
            self.name = name
            self.arguments = arguments

    actions = guard.check([
        _TC("invoke", {"code": "print('a')  # v1\n"}),      # noqa: FURB129
    ])
    assert actions == []
    actions = guard.check([
        _TC("invoke", {"code": "print('a')  # v2\n"}),       # noqa: FURB129
    ])
    assert actions == []
    # Third near-identical snippet crosses the threshold and warns.
    actions = guard.check([
        _TC("invoke", {"code": "print('a')  # v3\n"}),       # noqa: FURB129
    ])
    assert actions and actions[0].warning_type == "near_identical_calls"