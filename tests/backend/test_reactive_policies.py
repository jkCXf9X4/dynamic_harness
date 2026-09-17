from __future__ import annotations

from typing import Any

import pytest

from dynamic_harness.core.policies.brief import BriefPolicy
from dynamic_harness.core.policies.interface import (
    Observation,
    PromptInjection,
    ReactivePolicy,
    ReactivePolicyRegistry,
)
from dynamic_harness.core.policies.loop_guard import LoopGuard
from dynamic_harness.core.policies.nudge import NudgePolicy
from dynamic_harness.core.policies.spawn import SpawnPolicy, SpawnWarningPolicy
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import Task
from dynamic_harness.llm.provider import LLMProvider, ToolCallData, ToolCallResponse


def _obs(**kw: Any) -> Observation:
    base: dict[str, Any] = dict(
        iteration=0,
        max_iterations=500,
        has_delegated=True,
        tool_calls=[],
    )
    base.update(kw)
    return Observation(**base)


# ── the shared vocabulary -------------------------------------------------


def test_prompt_injection_levels_and_stop() -> None:
    assert PromptInjection.notice("n", warning_type="w").level == "notice"
    assert PromptInjection.notice("n", warning_type="w").stop is False
    assert PromptInjection.warning("w", warning_type="w").level == "warning"
    c = PromptInjection.critical("stop", warning_type="loop")
    assert c.level == "critical"
    assert c.stop is True


# ── the registry -----------------------------------------------------------


class _Fires:
    name: str

    def __init__(self, name: str, fire_at: int) -> None:
        self.name = name
        self.fire_at = fire_at
        self.calls = 0

    def evaluate(self, obs: Observation) -> PromptInjection | None:
        self.calls += 1
        if obs.iteration >= self.fire_at:
            return PromptInjection.notice(f"{self.name} fired", warning_type=self.name)
        return None


def test_registry_add_evaluate_flattens_in_order() -> None:
    reg = ReactivePolicyRegistry(_Fires("a", 0), _Fires("b", 0))
    obs = _obs(iteration=1)
    out = reg.evaluate_all(obs)
    assert [i.message for i in out] == ["a fired", "b fired"]
    assert reg.names() == ["a", "b"]


def test_registry_replaces_by_name() -> None:
    reg = ReactivePolicyRegistry(_Fires("a", 0))
    reg.add(_Fires("a", 99))
    assert reg.names() == ["a"]
    assert reg.evaluate_all(_obs(iteration=0)) == []
    assert reg.get("a") is not None
    reg.unregister("a")
    assert reg.names() == []


def test_registry_skips_none_and_accepts_list() -> None:
    class _Listy(_Fires):
        def evaluate(self, obs: Observation) -> list[PromptInjection]:
            return [PromptInjection.notice("x", warning_type=self.name),
                    PromptInjection.notice("y", warning_type=self.name)]

    reg = ReactivePolicyRegistry(_Listy("l", 0))
    assert [i.message for i in reg.evaluate_all(_obs(iteration=0))] == ["x", "y"]


# ── NudgePolicy as a reactive policy --------------------------------------


def test_nudge_policy_evaluate_fires_and_consumes_budget() -> None:
    pol = NudgePolicy(delegate_nudge_threshold=3, delegate_nudge_attempts=1)
    obs = _obs(iteration=5, has_delegated=False, max_iterations=500)
    first = pol.evaluate(obs)
    assert len(first) == 1
    assert first[0].warning_type == "delegate_reminder"
    assert pol.delegate_nudge_left == 0
    # Budget consumed: the same observation no longer fires.
    assert pol.evaluate(obs) == []


def test_nudge_policy_evaluate_low_iteration_warning() -> None:
    pol = NudgePolicy(
        iteration_warning_margin=10, iteration_warning_attempts=1, safety_max_iterations=100
    )
    out = pol.evaluate(_obs(iteration=95, max_iterations=100))
    assert len(out) == 1
    assert out[0].warning_type == "iterations_running_low"
    assert "iteration budget is almost exhausted" in out[0].message


def test_nudge_policy_evaluate_skips_delegating_agents() -> None:
    pol = NudgePolicy(delegate_nudge_threshold=3, delegate_nudge_attempts=1)
    assert pol.evaluate(_obs(iteration=5, has_delegated=True)) == []


# ── LoopGuard as a reactive policy ----------------------------------------


def test_loop_guard_evaluate_maps_to_critical() -> None:
    guard = LoopGuard(repeated_call_limit=3, repeated_recovery_attempts=0)
    responses: list[ToolCallResponse] = []
    for i in range(3):
        responses.append(ToolCallResponse(
            content=None,
            model="mock",
            tool_calls=[ToolCallData(id=f"c{i}", name="grep", arguments={"pattern": "x"})],
        ))
    # First two passes: only detection bookkeeping, no directive.
    for resp in responses[:2]:
        obs = _obs(iteration=1, tool_calls=resp.tool_calls, assistant_content=resp.content)
        assert guard.evaluate(obs) == []
    obs = _obs(iteration=3, tool_calls=responses[2].tool_calls,
               assistant_content=responses[2].content)
    out = guard.evaluate(obs)
    assert len(out) == 1
    assert out[0].stop is True
    assert out[0].level == "critical"


def test_loop_guard_evaluate_notice_for_near_identical() -> None:
    guard = LoopGuard(
        repeated_call_limit=50,
        repeated_recovery_attempts=0,
        near_identical_threshold=2,
        near_identical_window=4,
        near_identical_warning_attempts=1,
    )
    calls = [
        ToolCallResponse(content=None, model="mock", tool_calls=[ToolCallData(
            id="a", name="bash", arguments={"command": "sed -n '1,20p' /workspace/foo.py"})]),
        ToolCallResponse(content=None, model="mock", tool_calls=[ToolCallData(
            id="b", name="bash", arguments={"command": "cat /workspace/foo.py"})]),
    ]
    # The re-read of the same file through a second wrapper is already the
    # near-identical signal → a non-fatal notice fires on the second pass.
    guard.evaluate(_obs(iteration=1, tool_calls=calls[0].tool_calls))
    obs = _obs(iteration=2, tool_calls=calls[1].tool_calls)
    out = guard.evaluate(obs)
    assert any(i.warning_type == "near_identical_calls" and not i.stop for i in out)


# ── BriefPolicy as a reactive policy -------------------------------------


def test_brief_policy_fires_on_delegate_without_intent_dimension() -> None:
    """A delegate() call that omits intent/end_state triggers a notice naming
    the missing dimension(s); a fully briefed delegation stays silent."""
    pol = BriefPolicy(brief_nudge_attempts=1)
    tc = ToolCallData(id="d1", name="delegate", arguments={"description": "audit auth"})
    out = pol.evaluate(_obs(iteration=1, tool_calls=[tc]))
    assert len(out) == 1
    assert out[0].warning_type == "mission_brief"
    assert "intent, end_state" in out[0].message
    assert pol.brief_nudge_left == 0
    # Budget consumed: silent on a later turn even if it keeps under-briefing.
    assert pol.evaluate(_obs(iteration=2, tool_calls=[tc])) == []


def test_brief_policy_silent_when_intent_and_end_state_present() -> None:
    pol = BriefPolicy()
    tc = ToolCallData(
        id="d1", name="delegate",
        arguments={
            "description": "audit auth",
            "intent": "the release depends on auth",
            "end_state": "a verdict per finding in audit.md",
        },
    )
    assert pol.evaluate(_obs(iteration=1, tool_calls=[tc])) == []


def test_brief_policy_names_only_missing_dimension() -> None:
    pol = BriefPolicy()
    tc = ToolCallData(
        id="d1", name="delegate",
        arguments={"description": "audit auth", "end_state": "done.md"},
    )
    out = pol.evaluate(_obs(iteration=1, tool_calls=[tc]))
    assert len(out) == 1
    assert out[0].data is not None
    assert out[0].data["missing"] == ["intent"]


def test_brief_policy_ignores_non_delegate_calls_and_resets() -> None:
    pol = BriefPolicy(brief_nudge_attempts=1)
    usage_tc = ToolCallData(id="u1", name="usage", arguments={})
    assert pol.evaluate(_obs(iteration=1, tool_calls=[usage_tc])) == []
    # One notice per turn regardless of how many under-briefed children spawn.
    tc = ToolCallData(id="d1", name="delegate", arguments={"description": "x"})
    assert len(pol.evaluate(_obs(iteration=2, tool_calls=[tc, tc]))) == 1
    # reset() restores the budget (fresh run).
    pol.reset()
    assert len(pol.evaluate(_obs(iteration=3, tool_calls=[tc]))) == 1


def test_brief_policy_disabled_at_zero_attempts() -> None:
    pol = BriefPolicy(brief_nudge_attempts=0)
    tc = ToolCallData(id="d1", name="delegate", arguments={"description": "x"})
    assert pol.evaluate(_obs(iteration=1, tool_calls=[tc])) == []


# ── SpawnWarningPolicy as a reactive policy -------------------------------


def test_spawn_warning_policy_fires_near_cap_notice() -> None:
    spawn = SpawnPolicy(max_agents=10, max_depth=5, max_same_target=7, warning_attempts=2)
    pol = SpawnWarningPolicy(spawn, warning_attempts=2)
    usage = {"agents": 9, "max_agents": 10, "depth": 1, "max_depth": 5,
             "max_same_target": 7, "top_same_targets": []}
    obs = _obs(iteration=1, tree_depth=1, spawn_usage=usage)
    out = pol.evaluate(obs)
    assert len(out) == 1
    assert out[0].warning_type == "spawn_limits_near_cap"
    assert "You are approaching the delegation caps" in out[0].message
    # Budget (2) spent after two fires; the third observation is silent.
    assert pol.evaluate(obs)
    assert pol.evaluate(obs) == []


def test_spawn_warning_policy_silent_below_cap() -> None:
    spawn = SpawnPolicy(max_agents=10, warning_attempts=1)
    pol = SpawnWarningPolicy(spawn, warning_attempts=1)
    obs = _obs(iteration=1, spawn_usage={"agents": 2, "max_agents": 10})
    assert pol.evaluate(obs) == []


# ── wiring through the agent / runtime ------------------------------------


class _ScriptedLLM(LLMProvider):
    def __init__(self, responses: list[ToolCallResponse]) -> None:
        self.responses = list(responses)
        self.call_count = 0

    async def generate(self, system: str, user: str, config=None):
        raise NotImplementedError

    async def generate_structured(self, system: str, user: str, response_model, config=None):
        raise NotImplementedError

    async def generate_with_tools(self, messages: list[dict], tools: list[dict], config=None):
        resp = self.responses[min(self.call_count, len(self.responses) - 1)]
        self.call_count += 1
        return resp


def _usage_call(i: int) -> ToolCallResponse:
    return ToolCallResponse(
        content=None,
        model="mock",
        tool_calls=[ToolCallData(id=f"usage_{i}", name="usage", arguments={})],
    )


@pytest.mark.asyncio
async def test_agent_applies_host_registered_critical_policy(runtime: Runtime) -> None:
    """A host-registered reactive policy's critical directive fails the run."""
    fired: list[bool] = []

    def make_policy() -> ReactivePolicy:
        pol = _Fires("plugin_stop", 0)

        def evaluate(obs: Observation) -> PromptInjection | None:
            fired.append(True)
            return PromptInjection.critical("stop now per plugin", warning_type="plugin_stop")

        pol.evaluate = evaluate  # type: ignore[method-assign]
        return pol

    runtime.register_reactive_policy(make_policy)
    llm = _ScriptedLLM([_usage_call(0), _usage_call(1)])
    runtime.set_llm(llm)

    root = runtime.delegate(Task(description="run once"))
    await root.run()

    assert root.task.status.value == "failed"
    assert root.last_failure is not None
    assert "stop now per plugin" in root.last_failure.error
    assert fired


@pytest.mark.asyncio
async def test_agent_warning_injection_lands_then_reports(runtime: Runtime) -> None:
    """A plugin's warning directive is appended to the context before the agent
    reports, and the run carries on."""
    runtime.register_reactive_policy(lambda: _Fires("plugin_note", 1))

    llm = _ScriptedLLM([
        _usage_call(0),
        ToolCallResponse(content="finished", model="mock", tool_calls=[]),
    ])
    runtime.set_llm(llm)

    root = runtime.delegate(Task(description="run once"))
    await root.run()

    assert root.task.status.value == "completed"
    assert any(
        m.get("role") == "user" and "plugin_note fired" in str(m.get("content", ""))
        for m in root.context.messages
    )


@pytest.mark.asyncio
async def test_agent_brief_notice_injected_on_bare_delegation(tmp_path: Path) -> None:
    """A parent that delegates without intent/end_state gets one mission-brief
    notice appended to its context (tail-append-only), and the run continues."""
    from dynamic_harness.config import AgentConfig, HarnessConfig

    runtime = Runtime(
        artifact_root=tmp_path / "artifacts", repo_root=tmp_path / "repo",
        generated_root=tmp_path,
        config=HarnessConfig(agent=AgentConfig(stream_children=False)),
    )
    runtime.set_llm(_ScriptedLLM([
        # 1: parent delegates a bare task (no intent/end_state).
        ToolCallResponse(content=None, model="mock", tool_calls=[ToolCallData(
            id="p0", name="delegate", arguments={"description": "audit auth"})]),
        # 2: the child reports (synchronous gather, non-streaming).
        ToolCallResponse(content=None, model="mock", tool_calls=[ToolCallData(
            id="c0", name="report",
            arguments={"summary": "child done", "files_written": ["audit.md"]})]),
        # 3: the parent reports.
        ToolCallResponse(content=None, model="mock", tool_calls=[ToolCallData(
            id="p1", name="report",
            arguments={"summary": "all done", "files_written": ["out.md"]})]),
    ]))

    root = runtime.delegate(Task(description="parent"))
    await root.run()

    assert root.task.status.value == "completed"
    assert any(
        m.get("role") == "user" and "[brief]" in str(m.get("content", ""))
        and "mission-command intent dimension" in str(m.get("content", ""))
        for m in root.context.messages
    )


@pytest.mark.asyncio
async def test_runtime_policy_installed_fresh_per_agent(runtime: Runtime) -> None:
    """Every spawned agent gets its OWN instance of a host-registered policy."""
    instances: list[_Fires] = []

    def factory() -> ReactivePolicy:
        pol = _Fires("per_agent", 0)
        instances.append(pol)
        return pol

    runtime.register_reactive_policy(factory)
    a1 = runtime.delegate(Task(description="one"))
    a2 = runtime.delegate(Task(description="two"))

    assert a1.reactive_policies.get("per_agent") is not None
    assert a2.reactive_policies.get("per_agent") is not None
    assert a1.reactive_policies.get("per_agent") is not a2.reactive_policies.get("per_agent")
    assert len(instances) == 2


def test_agent_reactive_registry_listed_names(runtime: Runtime) -> None:
    agent = runtime.delegate(Task(description="x"))
    assert "nudges" in agent.reactive_policies.names()
    assert "mission_brief" in agent.reactive_policies.names()
    assert "spawn_warning" in agent.reactive_policies.names()
    # LoopGuard is driven at commit time, not via the post-turn registry.
    assert "loop_guard" not in agent.reactive_policies.names()