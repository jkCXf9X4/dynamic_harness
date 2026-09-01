from __future__ import annotations

import json

import pytest

from dynamic_harness.config import HarnessConfig, SafetyConfig, SelfHealConfig
from dynamic_harness.core.agent import Agent
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.spawn_limits import (
    DelegationLimit,
    SpawnLedger,
    delegate_target_signature,
)
from dynamic_harness.core.task import ReportPayload, Task
from dynamic_harness.llm.provider import LLMProvider, ToolCallData, ToolCallResponse


def make_runtime(tmp, **safety_kwargs):
    """Runtime with a custom SafetyConfig and self-heal disabled by default."""
    safety_kwargs.setdefault("max_agents", 50)
    safety_kwargs.setdefault("max_depth", 25)
    safety_kwargs.setdefault("max_same_target_delegations", 15)
    safety_kwargs.setdefault("spawn_limit_warning_attempts", 0)
    safety_kwargs.setdefault("repeated_call_limit", 100)
    cfg = HarnessConfig(
        safety=SafetyConfig(**safety_kwargs),
        self_heal=SelfHealConfig(mode=False, max_resumes=0, max_fresh_retries=0),
    )
    return Runtime(
        artifact_root=tmp / "artifacts",
        repo_root=tmp / "repo",
        generated_root=tmp,
        config=cfg,
    )


class _OKChild(Agent):
    """A child that reports immediately without touching the LLM."""

    async def run(self) -> None:
        self.report(ReportPayload(task_id=self.task.id, summary="ok"))


class _FailThenStopLLM(LLMProvider):
    """Emits delegate calls for one target until a refusal surfaces, then reports.

    Varies the wording slightly each turn so in-context repeated-call detection
    does not trip — but the extracted target path (and therefore the same-target
    scheduled cap) stays identical.
    """

    def __init__(self, description: str, target_path: str) -> None:
        self.description = description
        self.target_path = target_path
        self.tool_calls_issued = 0
        self.saw_refusal = False

    async def generate(self, system: str, user: str, config=None):
        raise NotImplementedError

    async def generate_with_tools(self, messages: list[dict], tools: list[dict], config=None):
        tool_msgs = [m for m in messages if isinstance(m, dict) and m.get("role") == "tool"]
        for tm in tool_msgs:
            content = str(tm.get("content", ""))
            if "refused" in content and "status" in content:
                self.saw_refusal = True
        if self.saw_refusal:
            return ToolCallResponse(content="all targets attempted; reporting now", model="mock")
        self.tool_calls_issued += 1
        # Identical extracted path, superficially different wording.
        desc = f"{self.description} {self.target_path} pass {self.tool_calls_issued} from a fresh angle"
        return ToolCallResponse(
            content=None,
            model="mock",
            tool_calls=[
                ToolCallData(
                    id=f"deleg_{self.tool_calls_issued}",
                    name="delegate",
                    arguments={"description": desc, "agent_type": "_OKChild"},
                )
            ],
        )

    async def generate_structured(self, system: str, user: str, response_model, config=None):
        raise NotImplementedError


class _NoopLLM(LLMProvider):
    """Never actually called by the code under test — just satisfies the
    ``self._llm is None`` self-heal guard so ``_recover`` proceeds."""

    async def generate(self, system: str, user: str, config=None):
        raise NotImplementedError

    async def generate_with_tools(self, messages: list[dict], tools: list[dict], config=None):
        return ToolCallResponse(content="done", model="mock")

    async def generate_structured(self, system: str, user: str, response_model, config=None):
        raise NotImplementedError


# -- signature extraction ---------------------------------------------------


def test_signature_extracts_file_and_directory_paths() -> None:
    sig = delegate_target_signature(
        "Explore the repository at /home/eriro/work/agentic_trading (READ-ONLY) "
        "and read docs/roadmap/LIVE_CAPITAL_READINESS.md in full"
    )
    assert "/home/eriro/work/agentic_trading" in sig
    assert "docs/roadmap/LIVE_CAPITAL_READINESS.md" in sig


def test_signature_stable_across_wording() -> None:
    a = delegate_target_signature("Read /repo/docs_improvement.md verbatim and return it")
    b = delegate_target_signature("re-read /repo/docs_improvement.md from offset 2000")
    assert a == b
    assert "docs_improvement.md" in a


def test_signature_differs_across_targets() -> None:
    assert delegate_target_signature("explore /repo/a") != delegate_target_signature(
        "explore /repo/b"
    )


# -- total-agent cap (A) ----------------------------------------------------


def test_max_agents_cap_refuses_direct_delegate(tmp) -> None:
    runtime = make_runtime(tmp, max_agents=3)

    root = runtime.delegate(Task(description="parent"))
    runtime.delegate(Task(description="child-1"), parent=root)
    runtime.delegate(Task(description="child-2"), parent=root)
    assert runtime.agent_count() == 3

    with pytest.raises(DelegationLimit) as exc:
        runtime.delegate(Task(description="child-3"), parent=root)
    assert "agent limit reached" in exc.value.reason
    # No phantom agent was registered and the task graph is untouched.
    assert runtime.agent_count() == 3
    assert root.id in runtime.task_graph()
    assert len(runtime.task_graph()[root.id]) == 2


def test_max_agents_cap_scope_is_total_not_per_parent(tmp) -> None:
    runtime = make_runtime(tmp, max_agents=6)
    r1 = runtime.delegate(Task(description="r1"))
    r2 = runtime.delegate(Task(description="r2"))
    for i in range(4):
        runtime.delegate(Task(description=f"r1-c{i}"), parent=r1)
    assert runtime.agent_count() == 6
    with pytest.raises(DelegationLimit):
        runtime.delegate(Task(description="r2-c0"), parent=r2)


# -- depth cap (B) ----------------------------------------------------------


def test_max_depth_cap_refuses_deep_chain(tmp) -> None:
    runtime = make_runtime(tmp, max_depth=3)

    root = runtime.delegate(Task(description="root"))
    assert root._depth == 0
    n1 = runtime.delegate(Task(description="explore /repo/x lvl1"), parent=root)
    n2 = runtime.delegate(Task(description="explore /repo/x lvl2"), parent=n1)
    n3 = runtime.delegate(Task(description="explore /repo/x lvl3"), parent=n2)
    assert n3._depth == 3

    with pytest.raises(DelegationLimit) as exc:
        runtime.delegate(Task(description="explore /repo/x lvl4"), parent=n3)
    assert "tree depth limit" in exc.value.reason
    assert runtime.agent_count() == 4


# -- same-target cap (C) ----------------------------------------------------


def test_max_same_target_cap_is_lineage_scoped(tmp) -> None:
    runtime = make_runtime(tmp, max_same_target_delegations=3)

    root = runtime.delegate(Task(description="parent"))
    for i in range(3):
        runtime.delegate(Task(description=f"explore /repo/shared step {i}"), parent=root)
    with pytest.raises(DelegationLimit):
        runtime.delegate(Task(description="explore /repo/shared step 4"), parent=root)
    # A different target is still allowed.
    runtime.delegate(Task(description="explore /repo/other area"), parent=root)

    # A separate lineage starts a fresh ledger and may use its own budget.
    root2 = runtime.delegate(Task(description="second lineage"))
    child = runtime.delegate(Task(description="explore /repo/shared from lineage 2"), parent=root2)
    assert child._spawn_ledger is not root._spawn_ledger
    runtime.delegate(Task(description="explore /repo/shared from lineage 2 b"), parent=root2)


def test_same_target_cap_ignores_targetless_descriptions(tmp) -> None:
    runtime = make_runtime(tmp, max_same_target_delegations=3)
    root = runtime.delegate(Task(description="parent"))
    for i in range(10):
        runtime.delegate(Task(description=f"plain objective number {i}"), parent=root)
    assert runtime.agent_count() == 11


# -- delegate tool refusal --------------------------------------------------


@pytest.mark.asyncio
async def test_delegate_tool_refuses_and_reports_budget(tmp) -> None:
    runtime = make_runtime(tmp, max_same_target_delegations=2)
    runtime.register_agent_class("_OKChild", _OKChild)
    root = runtime.delegate(Task(description="orchestrate"))

    for i in range(2):
        result = json.loads(
            await await_tool(root, f"explore /repo/x pass {i}", tool_call_id=f"c{i}")
        )
        assert result["status"] not in ("refused",)
        assert "budget" in result and "agents" in result["budget"]

    refused = json.loads(await await_tool(root, "explore /repo/x pass 3", tool_call_id="c3"))
    assert refused["status"] == "refused"
    assert len(runtime.task_graph()[root.id]) == 2
    assert runtime.agent_count() == 3  # root + two children; the refused one never existed
    assert "budget" in refused

    # The model is told to finish in-context / escalate, and NOT to retry.
    assert "in-context" in refused["suggestion"]
    assert "do NOT call delegate()" in refused["suggestion"]


@pytest.mark.asyncio
async def test_delegate_tool_allowed_different_target_after_refusal(tmp) -> None:
    runtime = make_runtime(tmp, max_same_target_delegations=1)
    runtime.register_agent_class("_OKChild", _OKChild)
    root = runtime.delegate(Task(description="orchestrate"))

    first = json.loads(await await_tool(root, "explore /repo/x once", "a1"))
    assert first["status"] != "refused"
    refused = json.loads(await await_tool(root, "explore /repo/x twice", "a2"))
    assert refused["status"] == "refused"
    ok = json.loads(await await_tool(root, "explore /repo/y different", "a3"))
    assert ok["status"] != "refused"


# -- self-heal interplay ----------------------------------------------------


@pytest.mark.asyncio
async def test_self_heal_fresh_restart_refused_when_capped(tmp) -> None:
    cfg = HarnessConfig(
        safety=SafetyConfig(max_agents=1, max_same_target_delegations=50, repeated_call_limit=100),
        self_heal=SelfHealConfig(mode=True, max_resumes=0, max_fresh_retries=2),
    )
    runtime = Runtime(
        artifact_root=tmp / "a2", repo_root=tmp / "r2",
        generated_root=tmp / "g2", config=cfg,
    )

    class _Failing(Agent):
        async def run(self) -> None:
            self.fail("boom")

    runtime.register_agent_class("_Failing", _Failing)
    # ``_recover`` refuses to heal when no LLM is configured; a dummy provider
    # lets the fresh-restart layer run (it never actually invokes the LLM).
    runtime.set_llm(_NoopLLM())
    heal_events: list[str] = []
    runtime.on_activity(
        lambda e: heal_events.append(e.data.get("action") or e.data.get("warning_type", ""))
    )

    root = runtime.delegate(Task(description="explore /repo/x root"), agent_type="_Failing")
    await root.run()
    assert root.task.status.value == "failed"

    recovered = await runtime._recover(root)
    # The fresh restart re-delegates the same task but the total-agent cap is
    # exhausted -> the spawn is refused and the failed agent is left in place
    # (bounded out) instead of spawning an agent that should never exist.
    assert recovered is root
    assert "fresh_refused" in heal_events
    assert runtime.agent_count() == 1


# -- near-cap soft warning + full loop --------------------------------------


@pytest.mark.asyncio
async def test_near_cap_warning_injected_before_refusal(tmp) -> None:
    runtime = make_runtime(
        tmp,
        max_same_target_delegations=4,
        spawn_limit_warning_attempts=1,
        repeated_call_limit=100,
    )
    runtime.register_agent_class("_OKChild", _OKChild)
    llm = _FailThenStopLLM("explore the repository at", "/repo/x")
    runtime.set_llm(llm)

    root = runtime.delegate(Task(description="orchestrate a review"))
    await root.run()

    assert root.task.status.value == "completed"
    assert llm.saw_refusal is True
    # The non-fatal near-cap notice was injected before the hard refusal.
    assert any(
        m.get("role") == "user"
        and "You are approaching the delegation caps" in str(m.get("content", ""))
        for m in root.context.messages
    )
    usage = runtime.spawn_usage(root)
    assert usage["agents"] == 5  # root + the 4 _OKChildren that were created
    assert any(t["count"] >= 4 for t in usage["top_same_targets"])


# -- helpers / defaults -----------------------------------------------------


async def await_tool(agent: Agent, description: str, tool_call_id: str) -> str:
    result = await agent.run_delegate_tool(
        description, tool_call_id=tool_call_id, agent_type="_OKChild"
    )
    return result


def test_safety_config_defaults() -> None:
    s = SafetyConfig()
    assert s.max_agents == 200
    assert s.max_depth == 15
    assert s.max_same_target_delegations == 7
    assert s.spawn_limit_warning_attempts == 2


def test_same_target_cap_disabled_at_zero(tmp) -> None:
    runtime = make_runtime(tmp, max_same_target_delegations=0)
    assert runtime._max_same_target is None

    root = runtime.delegate(Task(description="parent"))
    for i in range(10):
        runtime.delegate(Task(description=f"explore /repo/shared pass {i}"), parent=root)
    assert runtime.agent_count() == 11


@pytest.mark.asyncio
async def test_delegate_tool_allows_same_target_when_zero(tmp) -> None:
    runtime = make_runtime(tmp, max_same_target_delegations=0)
    runtime.register_agent_class("_OKChild", _OKChild)
    root = runtime.delegate(Task(description="orchestrate"))
    for i in range(10):
        result = json.loads(
            await await_tool(root, f"explore /repo/x pass {i}", tool_call_id=f"c{i}")
        )
        assert result["status"] != "refused"
    assert runtime.agent_count() == 11


def test_spawn_ledger_counts_by_signature() -> None:
    ledger = SpawnLedger()
    assert ledger.count("a") == 0
    for _ in range(3):
        ledger.record("a")
    ledger.record("b")
    assert ledger.count("a") == 3
    assert ledger.total_recorded() == 4
    assert ledger.top_targets(1) == [("a", 3)]