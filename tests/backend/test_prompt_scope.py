from __future__ import annotations

import re

import pytest

from dynamic_harness.core.prompts import AGENT_SYSTEM_PROMPT, ORCHESTRATOR_SYSTEM_PROMPT
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import TaskStatus
from dynamic_harness.llm.provider import LLMProvider, ToolCallData, ToolCallResponse

ROOT_DESC = "build a monitoring dashboard"
SCOPER_DESC = "Produce a scoping brief for: build a monitoring dashboard"
WORKER_DESC = "Implement the monitoring dashboard per the scoping brief"

SCOPER_BRIEF = (
    "INTENT: surface service health so operators can act before outages\n"
    "END STATE: a working dashboard page backed by real metrics\n"
    "CONSTRAINTS: no external services; read metrics from localhost\n"
    "ACCEPTANCE: all status checks green"
)


class _ScopeFirstLLM(LLMProvider):
    """Follows the scope-before-work pattern mandated by the prompts.

    Shared by every agent in the run; routes on the agent's task description
    (the last user message). Root: delegate scoping -> read the scoper's
    artifact -> delegate the work carrying the brief -> report. Scoper and
    worker settle with a report each.
    """

    def __init__(self) -> None:
        self.root_calls = 0
        self.scoper_calls = 0
        self.worker_calls = 0
        self.work_delegate_args: dict | None = None

    async def generate(self, system: str, user: str, config=None):
        raise NotImplementedError

    async def generate_structured(self, system, user, response_model, config=None):
        raise NotImplementedError

    @staticmethod
    def _task_text(messages: list[dict]) -> str:
        # The first user message is always the agent's task description (later
        # user messages may be framework injections: [brief], [child settled]…);
        # a role may prefix it as "[ROLE] …\n\n[TASK] …".
        for m in messages:
            if m.get("role") == "user" and isinstance(m.get("content"), str):
                text = m["content"]
                marker = "\n\n[TASK] "
                if marker in text:
                    return text.rsplit(marker, 1)[1]
                return text
        return ""

    @staticmethod
    def _child_id_from_results(messages: list[dict]) -> str:
        for m in messages:
            if m.get("role") == "tool" and isinstance(m.get("content"), str):
                hit = re.search(r'"child_id":\s*"([0-9a-f]{12})"', m["content"])
                if hit:
                    return hit.group(1)
        raise AssertionError("no delegate tool result with child_id found")

    async def generate_with_tools(self, messages, tools, config=None):
        text = self._task_text(messages)
        if text == ROOT_DESC:
            self.root_calls += 1
            if self.root_calls == 1:
                return ToolCallResponse(
                    content=None, model="mock",
                    tool_calls=[ToolCallData(
                        id="r1", name="delegate",
                        arguments={"description": SCOPER_DESC},
                    )],
                )
            if self.root_calls == 2:
                child_id = self._child_id_from_results(messages)
                return ToolCallResponse(
                    content=None, model="mock",
                    tool_calls=[ToolCallData(
                        id="r2", name="read_artifact",
                        arguments={"artifact_id": child_id},
                    )],
                )
            if self.root_calls == 3:
                self.work_delegate_args = {
                    "description": WORKER_DESC,
                    "intent": "surface service health so operators can act before outages",
                    "end_state": "a working dashboard page backed by real metrics",
                    "constraints": ["no external services", "read metrics from localhost"],
                    "authority": "adapt the layout; report deviations",
                }
                return ToolCallResponse(
                    content=None, model="mock",
                    tool_calls=[ToolCallData(
                        id="r3", name="delegate", arguments=self.work_delegate_args,
                    )],
                )
            if self.root_calls == 4:
                return ToolCallResponse(
                    content=None, model="mock",
                    tool_calls=[ToolCallData(
                        id="r4", name="report",
                        arguments={"summary": "dashboard delivered", "files_written": ["/summary.md"]},
                    )],
                )
        if text == SCOPER_DESC:
            self.scoper_calls += 1
            return ToolCallResponse(
                content=None, model="mock",
                tool_calls=[ToolCallData(
                    id="s1", name="report",
                    arguments={
                        "summary": "scoped",
                        "full_report": SCOPER_BRIEF,
                        "files_written": ["/brief.md"],
                    },
                )],
            )
        if text == WORKER_DESC:
            self.worker_calls += 1
            return ToolCallResponse(
                content=None, model="mock",
                tool_calls=[ToolCallData(
                    id="w1", name="report",
                    arguments={"summary": "dashboard built", "files_written": ["/dash.py"]},
                )],
            )
        raise AssertionError(f"unexpected task description: {text!r}")


class _ImmediateReportLLM(LLMProvider):
    """Reports on the first turn — the 'unambiguous and trivial' skip path."""

    async def generate(self, system: str, user: str, config=None):
        raise NotImplementedError

    async def generate_structured(self, system, user, response_model, config=None):
        raise NotImplementedError

    async def generate_with_tools(self, messages, tools, config=None):
        return ToolCallResponse(
            content=None, model="mock",
            tool_calls=[ToolCallData(
                id="c1", name="report",
                arguments={"summary": "trivial answer", "files_written": ["/answer.txt"]},
            )],
        )


def _sync_runtime(runtime: Runtime) -> Runtime:
    """A runtime with streaming children off, so delegation is the deterministic
    block-until-settled gather the scoping pattern relies on."""
    runtime._stream_children = False
    return runtime


def test_base_prompt_mandates_scope_before_work() -> None:
    assert "Scope before work" in AGENT_SYSTEM_PROMPT
    assert "One scoping agent per mission" in AGENT_SYSTEM_PROMPT
    assert "batch" in AGENT_SYSTEM_PROMPT


def test_orchestrator_prompt_mandates_scope_before_decompose() -> None:
    assert "SCOPE BEFORE DECOMPOSE" in ORCHESTRATOR_SYSTEM_PROMPT
    assert "scoping-brief sub-agent" in ORCHESTRATOR_SYSTEM_PROMPT
    assert "ask" in ORCHESTRATOR_SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_scope_before_work_flow(runtime: Runtime) -> None:
    llm = _ScopeFirstLLM()
    runtime = _sync_runtime(runtime)
    runtime.set_llm(llm)

    root = await runtime.run(ROOT_DESC)

    assert root.task.status == TaskStatus.completed
    assert root.last_report is not None
    assert llm.root_calls == 4          # scope -> verify -> work -> report
    assert llm.scoper_calls == 1
    assert llm.worker_calls == 1

    children = {c.task.description: c for c in root.children}
    scoper = children[SCOPER_DESC]
    worker = children[WORKER_DESC]

    # The scoping sub-agent produced a brief artifact for the parent to consume.
    assert scoper.last_report is not None
    assert "INTENT" in (scoper.last_report.full_report or "")

    # The worker carried the verified brief into its mission-command fields.
    assert worker.task.intent == llm.work_delegate_args["intent"]
    assert worker.task.end_state == llm.work_delegate_args["end_state"]
    assert worker.task.constraints == llm.work_delegate_args["constraints"]
    assert worker.task.authority == llm.work_delegate_args["authority"]

    # Task graph: root -> scoper + worker.
    graph = runtime.task_graph()
    assert len(graph[root.id]) == 2


@pytest.mark.asyncio
async def test_trivial_mission_skips_scoping(runtime: Runtime) -> None:
    llm = _ImmediateReportLLM()
    runtime = _sync_runtime(runtime)
    runtime.set_llm(llm)

    root = await runtime.run("what is 2+2")

    assert root.task.status == TaskStatus.completed
    assert root.last_report is not None
    assert "trivial answer" in root.last_report.summary
    assert runtime.agent_count() == 1  # no scoping agent spawned


@pytest.mark.asyncio
async def test_scope_pattern_works_for_orchestrator_root(runtime: Runtime) -> None:
    """The CLI promotes the root to the orchestrator role; the pattern must hold
    there too (its tool set includes delegate/ask/read_artifact)."""
    llm = _ScopeFirstLLM()
    runtime = _sync_runtime(runtime)
    runtime.set_llm(llm)

    from dynamic_harness.core.prompts import ORCHESTRATOR_ROLE

    root = await runtime.run(ROOT_DESC, role=ORCHESTRATOR_ROLE)

    assert root.task.status == TaskStatus.completed
    assert llm.scoper_calls == 1
    assert llm.worker_calls == 1
    assert root.children  # orchestrator delegated; never did the work itself