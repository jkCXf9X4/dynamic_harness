"""Regression tests for the use-case gap fixes (G3, G4, G6, G10)."""

from __future__ import annotations

import json

import pytest

from dynamic_harness.core.agent import Agent
from dynamic_harness.core.task import ReportPayload, Task


@pytest.mark.asyncio
async def test_g4_report_copies_written_files_into_artifact(runtime, tmp) -> None:
    """files_reported are stored inside the artifact dir so they survive and are
    reachable via read_artifact(file=...), making the artifact self-contained."""
    src = tmp / "findings.json"
    src.write_text('{"vuln": "HIGH"}')

    agent = runtime.delegate(Task(description="produce findings"))
    agent.report = lambda payload: runtime.deliver_report(agent.id, payload)
    await runtime.tool_registry.execute(
        "report", "tc1", agent=agent,
        summary="conscious of a vuln",
        files_written=[str(src)],
    )

    artifact_id = agent._report_artifact_id
    assert artifact_id is not None
    # file copied verbatim into the artifact dir
    stored = runtime.artifact_store.read_text(artifact_id, "findings.json")
    assert stored is not None and '"HIGH"' in stored

    # raw_data view is populated (G3) and surfaces the stored file
    art = runtime.artifact_store.get(artifact_id)
    assert art is not None and art.views.raw_data
    assert "findings.json" in art.views.raw_data

    # read_artifact(file=...) surfaces the stored copy
    parent = runtime.delegate(Task(description="parent"))
    result = await runtime.tool_registry.execute(
        "read_artifact", "tc2", agent=parent,
        artifact_id=artifact_id, file="findings.json")
    assert '"HIGH"' in result.content

    # provenance index lists the stored file (G4)
    idx_path = runtime.write_provenance_index()
    row = next(
        json.loads(line) for line in idx_path.read_text().splitlines()
        if json.loads(line)["artifact_id"] == artifact_id
    )
    assert "findings.json" in row["files_written"]


@pytest.mark.asyncio
async def test_g3_progressive_disclosure_levels(runtime) -> None:
    """read_artifact withholds detail by default and exposes deeper levels."""
    agent = runtime.delegate(Task(description="child"))
    agent.report = lambda payload: runtime.deliver_report(agent.id, payload)
    await runtime.tool_registry.execute(
        "report", "tc1", agent=agent,
        summary="short summary",
        technical_summary="TECH_BODY",
        full_report="VERY_LONG_FULL_REPORT_BODY",
    )
    artifact_id = agent._report_artifact_id

    parent = runtime.delegate(Task(description="parent"))
    default_result = await runtime.tool_registry.execute(
        "read_artifact", "tc2", agent=parent, artifact_id=artifact_id)
    assert "short summary" in default_result.content
    assert "VERY_LONG" not in default_result.content  # withheld

    full = await runtime.tool_registry.execute(
        "read_artifact", "tc3", agent=parent,
        artifact_id=artifact_id, level="full")
    assert "VERY_LONG_FULL_REPORT_BODY" in full.content

    # unknown level is an explicit error, not a silent fallback
    bad = await runtime.tool_registry.execute(
        "read_artifact", "tc4", agent=parent,
        artifact_id=artifact_id, level="bogus")
    assert "unknown level" in bad.content


@pytest.mark.asyncio
async def test_g6_delegate_tool_agent_type(runtime) -> None:
    """The LLM delegate tool accepts a registered agent_type and rejects
    unknown names instead of silently falling back to the base Agent."""
    class Specialist(Agent):
        async def run(self) -> None:
            self.report(ReportPayload(task_id=self.task.id, summary="specialist output"))

    runtime.register_agent_class("Specialist", Specialist)

    parent = runtime.delegate(Task(description="root"))
    ok = await runtime.tool_registry.execute(
        "delegate", "tc1", agent=parent,
        description="do disciplined work", agent_type="Specialist")
    assert "specialist output" in ok.content

    bad = await runtime.tool_registry.execute(
        "delegate", "tc2", agent=parent,
        description="do work", agent_type="NoSuchAgent")
    assert "unknown agent_type" in bad.content


@pytest.mark.asyncio
async def test_g10_message_count_is_cumulative(runtime) -> None:
    """message_count accumulates across record_usage calls (G10)."""
    await runtime.record_usage("a1", prompt_tokens=10, completion_tokens=10, message_count=5)
    await runtime.record_usage("a1", prompt_tokens=10, completion_tokens=10, message_count=3)
    usage = runtime.get_usage("a1")
    assert usage["message_count"] == 8  # 5 + 3, not 3