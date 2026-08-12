"""Tests locking in fixes from the 2026-08-11 codebase review.

Covers: event-handler failure isolation, injected (non-hardcoded) environment
info, webfetch SSRF/scheme validation, and the single context-observation slot.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dynamic_harness.config import HarnessConfig
from dynamic_harness.core.agent import Agent
from dynamic_harness.core.environment import build_environment_info
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import ReportPayload, Task


@pytest.mark.asyncio
async def test_raising_event_handler_does_not_fail_agent(runtime: Runtime) -> None:
    """A buggy UI/logger handler must not force-fail the agent that emitted it."""

    def boom(aid, payload):
        raise RuntimeError("handler bug")

    runtime.on_report(boom)

    class LeafAgent(Agent):
        async def run(self) -> None:
            self.report(ReportPayload(task_id=self.task.id, summary="done"))

    runtime.register_agent_class("LeafAgent", LeafAgent)
    root = runtime.delegate(Task(description="R"), agent_type="LeafAgent")
    await root.run()

    assert root.task.status.value == "completed"
    assert root.last_report is not None
    assert root.last_report.summary == "done"


def test_environment_info_is_injected_not_hardcoded(tmp_path: Path) -> None:
    """Agent environment comes from requested config notes, never stale constants."""
    config = HarnessConfig()
    config.agent.environment_notes = ["pip is unavailable", "run pytest from root"]
    rt = Runtime(
        artifact_root=tmp_path / "a",
        repo_root=tmp_path / "r",
        generated_root=tmp_path,
        config=config,
    )
    agent = rt.delegate(Task(description="T"))
    rendered = agent.environment_info
    assert "pip is unavailable" in rendered
    assert "run pytest from root" in rendered
    # The old hardcoded benchmark-era claims must not leak in by default.
    assert ".optimize_benchmarks" not in rendered
    cfg_default = HarnessConfig()
    assert cfg_default.agent.environment_notes == []


def test_webfetch_rejects_restricted_hosts() -> None:
    from dynamic_harness.core.tools.network import _validate_url

    assert _validate_url("http://127.0.0.1/admin") is not None
    assert _validate_url("https://192.168.1.10/x") is not None
    assert _validate_url("ftp://example.com/x") is not None
    assert _validate_url("https://example.com/x") is None


async def test_single_observation_slot(runtime: Runtime) -> None:
    """Only one context-observation message is kept, regardless of turns."""
    agent = runtime.delegate(Task(description="T"))
    agent.set_environment_info(build_environment_info())
    agent._set_observation(prompt_tokens=10)
    agent._set_observation(prompt_tokens=20)
    obs = [m for m in agent.context.messages if m.get("role") == "system"]
    assert len(obs) == 1
    assert "[Environment]" in obs[0]["content"]
