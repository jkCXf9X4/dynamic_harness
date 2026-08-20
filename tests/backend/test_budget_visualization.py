"""Regression tests for the token-budget awareness feature."""

from __future__ import annotations

import json

import pytest

from dynamic_harness.core.agent import Agent
from dynamic_harness.core.prompts import build_system_prompt
from dynamic_harness.core.task import Task
from dynamic_harness.core.tools.registry import ORCHESTRATOR_ALLOWED_TOOLS
from dynamic_harness.llm.provider import LLMProvider, ToolCallData, ToolCallResponse


class _ToolLLM(LLMProvider):
    """Always returns a tool call (keeps the loop alive for budget testing)."""

    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, system, user, config=None):
        raise NotImplementedError

    async def generate_with_tools(self, messages, tools, config=None):
        self.calls += 1
        return ToolCallResponse(
            content=None, model="mock",
            tool_calls=[ToolCallData(id=f"c{self.calls}", name="read", arguments={"path": "/x"})],
        )

    async def generate_structured(self, system, user, response_model, config=None):
        raise NotImplementedError


@pytest.mark.asyncio
async def test_usage_tool_reports_message_and_token_counters(runtime) -> None:
    """The usage tool returns live cumulative + live-context counters."""
    agent = runtime.delegate(Task(description="probe"))
    await runtime.record_usage(agent.id, message_count=5, prompt_tokens=120, completion_tokens=30)

    result = await runtime.tool_registry.execute("usage", "tc1", agent=agent)
    data = json.loads(result.content)
    assert data["cumulative_total_tokens"] == 150
    assert data["cumulative_messages_sent"] == 5
    assert data["max_agent_tokens"] is None
    assert "cumulative_prompt_tokens" in data

    # And orchestrators may check their own spend/counter too.
    assert "usage" in ORCHESTRATOR_ALLOWED_TOOLS


@pytest.mark.asyncio
async def test_max_agent_tokens_forces_budget_stop(runtime) -> None:
    """Exceeding the configured cap force-fails the agent (safety invariant)."""
    runtime.set_llm(_ToolLLM())
    root = runtime.delegate(Task(description="probe"))
    root.max_agent_tokens = 50  # tiny cap already exceeded
    await runtime.record_usage(root.id, prompt_tokens=40, completion_tokens=30)

    await root.run()

    assert root.task.status.value == "failed"
    assert root.last_failure is not None
    assert "budget" in root.last_failure.error.lower()


def test_budget_guidance_is_cache_friendly(runtime) -> None:
    """The cap is a static block folded into the system prefix, not a
    per-turn injected message (which would zero the provider prompt cache)."""
    assert "Budget" not in build_system_prompt("base", role=None)

    root = runtime.delegate(Task(description="probe"))
    root.max_agent_tokens = 50000
    steerage = root._build_steerage()
    assert "50000" in steerage
    assert "usage tool" in steerage