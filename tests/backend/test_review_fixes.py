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
from dynamic_harness.core.prompts import FocusLedger, render_focus
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


async def test_no_per_turn_observation_message(runtime: Runtime) -> None:
    """Steerage (env/focus) is folded into a STABLE leading system message so the
    conversation payload stays pure append-only and prompt caching survives."""
    agent = runtime.delegate(Task(description="T"))
    agent.set_environment_info(build_environment_info())
    agent.set_focus(objective="obj", deliverable="deliv")

    steerage = agent._build_steerage()
    assert "[Environment]" in steerage
    assert "[Focus] Objective: obj" in steerage
    assert "Deliverable: deliv" in steerage

    # There is no per-turn observation message anywhere in the payload contract.
    assert not any(
        isinstance(m.get("content"), str) and "Context Observation" in m["content"]
        for m in agent.context.messages
    )


def test_focus_renders_full_then_condensed() -> None:
    """Reminders pulse full detail, then collapse to objective+deliverable."""
    focus = FocusLedger(
        objective="Refactor module X",
        acceptance=["all tests green", "no new deps"],
        deliverable="write refactor.md and report()",
        pending=["step 3"],
        done=["step 1", "step 2"],
        pulse_interval=5,
    )
    full = render_focus(focus, iteration=1)
    assert "[Focus] Objective: Refactor module X" in full
    assert "Acceptance:" in full
    assert "Remaining: step 3" in full
    assert "Done so far:" in full
    assert "Deliverable:" in full

    between = render_focus(focus, iteration=3)
    assert "[Focus] Objective:" in between
    assert "Deliverable:" in between
    assert "Acceptance:" not in between
    assert "Remaining:" not in between

    pulsed = render_focus(focus, iteration=10)
    assert "Acceptance:" in pulsed


def test_focus_folded_into_system_prompt(runtime: Runtime) -> None:
    """Focus lands in the static system-prompt steerage (cacheable), not a
    per-turn observation message."""
    agent = runtime.delegate(Task(description="Long memory task"))
    agent.set_focus(
        acceptance=["a", "b"],
        deliverable="write out.txt and report()",
        pending=["p"],
        pulse_interval=10,
    )
    steerage = agent._build_steerage()
    assert "[Focus] Objective: Long memory task" in steerage
    assert "Deliverable: write out.txt and report()" in steerage
    # At reset (iteration 1) full acceptance detail is shown once.
    assert "Acceptance: a; b" in steerage


def test_focus_is_runtime_state_not_prompt_text(runtime: Runtime) -> None:
    """Reminders are rendered by code and appended to the system prompt,
    independent of the (optimizable) prompt body itself."""
    agent = runtime.delegate(Task(description="O", system_prompt="OPTIMIZED_TEXT"))
    agent.set_focus(objective="O", deliverable="D")
    steerage = agent._build_steerage()
    # "OPTIMIZED_TEXT" is the externally-optimizable prompt; the focus reminders
    # are separate, code-rendered steerage that survives prompt optimization.
    assert steerage != ""
    assert "OPTIMIZED_TEXT" not in steerage
    assert "[Focus] Objective: O" in steerage
    assert "Deliverable: D" in steerage
