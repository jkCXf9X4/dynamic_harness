"""Tests for the role-driven prompt composition and context instrumentation.

Covers: orchestrator role lookup (no more root override), conditional role tag,
the reconciled verification language, and the live-context token estimate.
"""

from __future__ import annotations

import asyncio

import pytest

from dynamic_harness.core.agent import Agent
from dynamic_harness.core.prompts import (
    AGENT_SYSTEM_PROMPT,
    ORCHESTRATOR_ROLE,
    ORCHESTRATOR_SYSTEM_PROMPT,
    build_system_prompt,
    build_user_message,
)
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import Task
from dynamic_harness.core.tools.registry import (
    ORCHESTRATOR_ALLOWED_TOOLS,
    tools_for_role,
)


def test_orchestrator_prompt_is_role_driven() -> None:
    """The delegation-only directive comes from role, not from being root."""
    base = "plain base prompt"
    with_role = build_system_prompt(base, role=ORCHESTRATOR_ROLE)
    assert "ORCHESTRATOR" in with_role
    assert base in with_role

    # A worker with no role must NOT receive the orchestrator directive.
    no_role = build_system_prompt(base, role=None)
    assert no_role == base
    assert "ORCHESTRATOR" not in no_role

    # A different role is scoped but is not an orchestrator, and must not
    # inherit the [ROLE]/scope double tag.
    other = build_system_prompt(base, role="Security Auditor")
    assert "ORCHESTRATOR" not in other
    assert "Security Auditor" in other


def test_orchestrator_prompt_is_depth_neutral() -> None:
    """An orchestrator may sit at any depth (sub-orchestrators supported)."""
    p = ORCHESTRATOR_SYSTEM_PROMPT.lower()
    assert "top-level" not in p
    assert "root agent" not in p
    assert "any depth" in p or "orchestrator" in p
    assert "report up" in p


def test_role_tag_omitted_when_no_role() -> None:
    """No role set -> no [ROLE] tag in either system prompt or user message."""
    base = "plain base prompt"
    no_role_sys = build_system_prompt(base, role=None)
    assert "[ROLE]" not in no_role_sys

    no_role_user = build_user_message("Do the thing", None)
    assert no_role_user == "Do the thing"

    # With a role set, the user message carries the tag (system prompt must not).
    with_role_user = build_user_message("Do the thing", "Security Auditor")
    assert "[ROLE] Security Auditor" in with_role_user
    assert "[ROLE]" not in build_system_prompt(base, role="Security Auditor")


def test_base_prompt_has_no_dead_role_placeholder() -> None:
    """The static prompt must not contain an uninterpolated [ROLE] token."""
    assert "[ROLE]" not in AGENT_SYSTEM_PROMPT


def test_verification_language_reconciled_with_context_economics() -> None:
    """Verification must prefer summaries / converse over pulling full bodies."""
    assert "progressive disclosure" in AGENT_SYSTEM_PROMPT.lower()
    assert "converse" in AGENT_SYSTEM_PROMPT
    assert "progressive disclosure" in ORCHESTRATOR_SYSTEM_PROMPT.lower()
    assert "prefer converse" in ORCHESTRATOR_SYSTEM_PROMPT.lower()


def test_orchestrator_role_in_production_prompt() -> None:
    """The shipped prompt wired up for orchestrator behavior."""
    built = build_system_prompt(AGENT_SYSTEM_PROMPT, role=ORCHESTRATOR_ROLE)
    assert "ORCHESTRATOR" in built


def test_delegate_tool_documents_sub_orchestrator() -> None:
    """The delegate tool points at 'orchestrator' for forced deeper decomposition."""
    from dynamic_harness.core.tools.agents import TOOL_DELEGATE_DEF

    doc = TOOL_DELEGATE_DEF.description
    schema = TOOL_DELEGATE_DEF.input_schema["properties"]["role"]["description"]
    assert "orchestrator" in doc.lower()
    assert "'orchestrator'" in schema or '"orchestrator"' in schema
    assert "sub-orchestrator" in doc.lower() + schema.lower()


def test_runtime_run_does_not_force_orchestrator(runtime: Runtime) -> None:
    """Low-level runtime.run() leaves the role explicit (CLI sets orchestrator)."""
    root = asyncio.run(runtime.run("work"))
    assert root.task.role is None


def test_agent_context_estimates_live_prompt_tokens(runtime: Runtime) -> None:
    """The observation token figure is a live estimate, not cumulative usage."""
    agent = runtime.delegate(Task(description="T"))
    agent.context.reset("[system]", "[user] T")
    assert agent.context.messages  # system + user seeded
    estimate = agent.context.estimate_prompt_tokens()
    assert estimate >= 1
    obs = agent._context_observation(estimate)
    assert "Estimated tokens in current live context" in obs
    assert "~" in obs


@pytest.mark.asyncio
async def test_orchestrator_tool_allowlist_blocks_worker_tools(runtime: Runtime) -> None:
    """An orchestrator physically cannot call worker tools (code-enforced)."""
    root = runtime.delegate(Task(description="work", role=ORCHESTRATOR_ROLE))
    schema_names = {s["function"]["name"] for s in runtime.tool_registry.openai_schemas(role=ORCHESTRATOR_ROLE)}
    assert "delegate" in schema_names
    assert "report" in schema_names
    for worker in ("read", "write", "bash", "webfetch", "glob", "grep", "edit"):
        assert worker not in schema_names, f"orchestrator schema should hide {worker}"

    res = await runtime.tool_registry.execute("bash", "tc1", root, command="echo hi")
    assert "not allowed" in res.content
    assert "delegate" in res.content
    res2 = await runtime.tool_registry.execute("delegate", "tc2", root, description="sub")
    assert "not allowed" not in res2.content


@pytest.mark.asyncio
async def test_worker_role_has_full_tools(runtime: Runtime) -> None:
    """A normal (non-orchestrator) agent keeps the full toolset."""
    worker = runtime.delegate(Task(description="work", role=None))
    schema_names = {s["function"]["name"] for s in runtime.tool_registry.openai_schemas(role=None)}
    assert "read" in schema_names
    assert "bash" in schema_names
    result = await runtime.tool_registry.execute("read", "tc1", worker, path="x")
    assert "not allowed" not in result.content


def test_tools_for_role_mapping() -> None:
    assert tools_for_role(None) is None
    assert tools_for_role("other") is None
    assert tools_for_role(ORCHESTRATOR_ROLE) == ORCHESTRATOR_ALLOWED_TOOLS