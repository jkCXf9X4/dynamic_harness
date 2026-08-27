from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Any

import pytest

from dynamic_harness.config import HarnessConfig, LLMProviderConfig, SafetyConfig
from dynamic_harness.core.agent import Agent
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import Task, TaskStatus
from dynamic_harness.llm.provider import LLMProvider, ToolCallData, ToolCallResponse


class _LoopToolLLM(LLMProvider):
    """Returns the same tool call every time to simulate a stuck agent."""

    def __init__(self, tool_name: str = "write", tool_args: dict | None = None, max_calls: int | None = None) -> None:
        self.tool_name = tool_name
        self.tool_args = tool_args or {"path": "/workspace/greeting.txt", "content": "hello"}
        self.max_calls = max_calls
        self.call_count = 0

    async def generate(self, system: str, user: str, config=None):
        raise NotImplementedError

    async def generate_with_tools(self, messages: list[dict], tools: list[dict], config=None):
        self.call_count += 1
        if self.max_calls is not None and self.call_count > self.max_calls:
            return ToolCallResponse(content="done", model="mock")
        return ToolCallResponse(
            content=None,
            model="mock",
            tool_calls=[
                ToolCallData(
                    id=f"call_{self.call_count}",
                    name=self.tool_name,
                    arguments=dict(self.tool_args),
                )
            ],
        )

    async def generate_structured(self, system: str, user: str, response_model, config=None):
        raise NotImplementedError


def _make_agent(
    runtime: Runtime,
    task: Task,
    safety_max_iterations: int = 50,
    repeated_call_limit: int = 5,
    repeated_recovery_attempts: int = 1,
    **kwargs,
) -> Agent:
    agent = Agent(
        "test-agent", task, runtime,
        safety_max_iterations=safety_max_iterations,
        repeated_call_limit=repeated_call_limit,
        repeated_recovery_attempts=repeated_recovery_attempts,
        **kwargs,
    )
    task.status = TaskStatus.running
    runtime._agents[agent.id] = agent
    return agent


@pytest.mark.asyncio
async def test_safety_max_iterations_limit_reached(runtime: Runtime) -> None:
    llm = _LoopToolLLM()
    runtime.set_llm(llm)

    root = _make_agent(runtime, Task(description="Looping task"), safety_max_iterations=5, repeated_call_limit=10)

    await root.run()

    assert root.task.status.value == "failed"


@pytest.mark.asyncio
async def test_low_iteration_warning_injected_before_hard_limit(runtime: Runtime) -> None:
    """With a small max-iterations cap, the agent gets a hard wrap-up notice
    injected into its context once it comes within the warning margin of the
    limit, telling it to finish off and hand remaining work to its parent."""
    llm = _LoopToolLLM()
    runtime.set_llm(llm)

    root = _make_agent(
        runtime, Task(description="Looping task"),
        safety_max_iterations=10, repeated_call_limit=100,
        iteration_warning_margin=5,
    )

    await root.run()

    assert root.task.status.value == "failed"
    # The wrap-up notice must have been appended as a user message the LLM saw,
    # before the hard limit was reached.
    assert any(
        m.get("role") == "user" and "iteration budget is almost exhausted" in str(m.get("content", ""))
        for m in root.context.messages
    )


@pytest.mark.asyncio
async def test_iteration_warning_fires_once(runtime: Runtime) -> None:
    """The low-iteration notice is injected at most once per run."""
    llm = _LoopToolLLM()
    runtime.set_llm(llm)

    root = _make_agent(
        runtime, Task(description="Looping task"),
        safety_max_iterations=10, repeated_call_limit=100,
        iteration_warning_margin=5,
    )

    await root.run()

    warnings = [
        m for m in root.context.messages
        if m.get("role") == "user"
        and "iteration budget is almost exhausted" in str(m.get("content", ""))
    ]
    assert len(warnings) == 1


@pytest.mark.asyncio
async def test_repeated_identical_calls_trigger_safety(runtime: Runtime) -> None:
    llm = _LoopToolLLM()
    runtime.set_llm(llm)

    root = _make_agent(runtime, Task(description="Looping task"), safety_max_iterations=100, repeated_call_limit=3)

    await root.run()

    assert root.task.status.value == "failed"


@pytest.mark.asyncio
async def test_loop_detection_nudges_once_before_failing(runtime: Runtime) -> None:
    """The agent is given one recovery chance before repeated-call detection
    force-fails it: a plain 'you are looping' user message is appended to its
    context and it gets another turn."""
    llm = _LoopToolLLM()
    runtime.set_llm(llm)

    root = _make_agent(runtime, Task(description="Looping task"), safety_max_iterations=100, repeated_call_limit=3, repeated_recovery_attempts=1)

    await root.run()

    assert root.task.status.value == "failed"
    assert root._repeated_calls_detected is True
    # The nudge must have been appended as a user message the LLM saw.
    assert any(
        m.get("role") == "user" and "You are looping" in str(m.get("content", ""))
        for m in root.context.messages
    )
    # With limit=3 the identical batch trips detection on the 3rd turn, but the
    # nudge buys one more turn before the 4th turn force-fails.
    assert llm.call_count >= 4


@pytest.mark.asyncio
async def test_agent_recovers_after_loop_nudge(runtime: Runtime) -> None:
    """A model that changes course after being told it is looping must not be
    force-failed: the run completes normally."""
    class RecoveringLLM(LLMProvider):
        def __init__(self):
            self.saw_nudge = False

        async def generate(self, system, user, config=None):
            raise NotImplementedError

        async def generate_with_tools(self, messages, tools, config=None):
            text = " ".join(str(m.get("content", "")) for m in messages if isinstance(m, dict))
            if "[safety] You are looping" in text:
                self.saw_nudge = True
                return ToolCallResponse(content="done writing the report", model="mock")
            return ToolCallResponse(
                content=None, model="mock",
                tool_calls=[ToolCallData(
                    id=f"c{self.saw_nudge}",
                    name="write",
                    arguments={"path": "/workspace/out.txt", "content": "final"},
                )],
            )

        async def generate_structured(self, system, user, response_model, config=None):
            raise NotImplementedError

    runtime.set_llm(RecoveringLLM())

    root = _make_agent(runtime, Task(description="Recovery task"), safety_max_iterations=100, repeated_call_limit=3)

    await root.run()

    assert root.task.status.value == "completed"
    assert root._repeated_calls_detected is True


@pytest.mark.asyncio
async def test_completes_when_tool_llm_finishes(runtime: Runtime) -> None:
    call_seq = [
        {"path": "/a.txt", "content": "1"},
        {"path": "/b.txt", "content": "2"},
    ]

    class VaryingToolLLM(LLMProvider):
        def __init__(self):
            self.idx = 0

        async def generate(self, system, user, config=None):
            raise NotImplementedError

        async def generate_with_tools(self, messages, tools, config=None):
            if self.idx >= len(call_seq):
                return ToolCallResponse(content="done", model="mock")
            args = call_seq[self.idx]
            self.idx += 1
            return ToolCallResponse(
                content=None,
                model="mock",
                tool_calls=[ToolCallData(id=f"call_{self.idx}", name="write", arguments=args)],
            )

        async def generate_structured(self, system, user, response_model, config=None):
            raise NotImplementedError

    llm = VaryingToolLLM()
    runtime.set_llm(llm)

    root = _make_agent(runtime, Task(description="Varying task"))

    await root.run()

    assert root.task.status.value == "completed"


@pytest.mark.asyncio
async def test_completes_normally_with_small_number_of_calls(runtime: Runtime) -> None:
    llm = _LoopToolLLM(max_calls=2)
    runtime.set_llm(llm)

    root = _make_agent(runtime, Task(description="Normal task"))

    await root.run()

    assert root.task.status.value == "completed"


def test_delegate_target_signature_extracts_path() -> None:
    sig = Agent._delegate_target_signature(
        {"description": "Read /repo/docs_improvement_analysis.md verbatim and return it"}
    )
    assert "docs_improvement_analysis.md" in sig

    # Different wording but same path -> same signature
    sig2 = Agent._delegate_target_signature(
        {"description": "re-read /repo/docs_improvement_analysis.md from offset 2000"}
    )
    assert sig2 == sig


@pytest.mark.asyncio
async def test_repeated_delegate_to_same_file_triggers_safety(runtime: Runtime) -> None:
    root = _make_agent(runtime, Task(description="orchestrate"),
                       repeated_call_limit=3, repeated_recovery_attempts=0)
    root._recent_batches = deque(maxlen=3)
    root.fail = lambda error, trace=None: root.outcome.__setattr__("failure", error)

    def resp(i: int):
        return ToolCallResponse(
            content=None, model="mock",
            tool_calls=[ToolCallData(
                id=f"c{i}", name="delegate",
                arguments={"description": f"read docs_improvement_analysis.md verbatim, attempt {i}"},
            )],
        )

    # Wording varies (attempt 1/2/3) but the file path is shared -> must trip.
    det = [root._check_repeated_calls(resp(i)) for i in range(1, 4)]
    assert det[0] is False and det[1] is False
    assert det[2] is True

    # Different targets never trip.
    root2 = _make_agent(runtime, Task(description="orchestrate"),
                        repeated_call_limit=3)
    root2._recent_batches = deque(maxlen=3)
    root2.fail = lambda error, trace=None: None
    for i in range(1, 6):
        ok = root2._check_repeated_calls(ToolCallResponse(
            content=None, model="mock",
            tool_calls=[ToolCallData(
                id=f"c{i}", name="delegate",
                arguments={"description": f"process file number {i}.md"},
            )],
        ))
        assert ok is False


@pytest.mark.asyncio
async def test_alternating_batches_trigger_sliding_window(runtime: Runtime) -> None:
    """Catch the trace failure mode: two near-identical command variants
    interleaved so no N batches are byte-identical, yet the same tool call
    recurs N times in a short window."""
    root = _make_agent(runtime, Task(description="loop"), repeated_call_limit=3,
                       repeated_recovery_attempts=0)
    root.fail = lambda error, trace=None: root.outcome.__setattr__("failure", error)

    def resp(i: int) -> ToolCallResponse:
        # two grep variants differing only by one extra term
        terms = "disclaimer|financial advice|educational"
        if i % 2 == 0:
            terms += "|risk of loss"
        args = {"command": f'grep -rn "{terms}" /repo'}
        return ToolCallResponse(
            content="check disclaimers", model="mock",
            tool_calls=[ToolCallData(id=f"c{i}", name="bash", arguments=args)],
        )

    det = [root._check_repeated_calls(resp(i)) for i in range(1, 6)]
    # first three should not trip (A,B,A); by the 5th call A recurs 3x in window
    assert det[2] is False
    assert det[4] is True


@pytest.mark.asyncio
async def test_identical_assistant_content_triggers(runtime: Runtime) -> None:
    """The model repeats the exact same text turn after turn while tool args
    fluctuate -- must still be flagged as a stuck loop."""
    root = _make_agent(runtime, Task(description="stuck"), repeated_call_limit=3)
    root.fail = lambda error, trace=None: root.outcome.__setattr__("failure", error)

    content = "Let me check the remaining README sections and the docs README disclaimer."
    for i in range(1, 7):
        ok = root._check_repeated_calls(ToolCallResponse(
            content=content, model="mock",
            tool_calls=[ToolCallData(
                id=f"c{i}", name="bash",
                arguments={"command": f"grep -n {i}"},
            )],
        ))
    # After enough identical-text turns in the window, the last call trips.
    # (limit=3 -> window=6; 6 identical msgs means last-3 identical.)
    assert root._repeated_calls_detected is True


def test_runtime_wires_timeout_from_config(tmp_path) -> None:
    cfg = HarnessConfig(safety=SafetyConfig(timeout_seconds=60.5))
    rt = Runtime(
        artifact_root=tmp_path / "artifacts",
        repo_root=tmp_path / "repo",
        generated_root=tmp_path,
        config=cfg,
    )
    assert rt._safety_timeout_seconds == 60.5
    assert rt._repeated_recovery_attempts == 1  # default
    task = Task(description="t")
    agent = rt.delegate(task)
    assert agent._safety_timeout_seconds == 60.5
    assert agent._repeated_recovery_left == 1


def test_root_exempt_from_timeout_but_children_inherit(tmp_path) -> None:
    """With disable_root_timeout, every root-level agent (parent is None) — the
    initial root AND any self-heal successor regenerating the tree — is exempt
    from the full-run wall-clock cap, while child agents still inherit it."""
    cfg = HarnessConfig(safety=SafetyConfig(
        timeout_seconds=60.5,
        disable_root_timeout=True,
    ))
    rt = Runtime(
        artifact_root=tmp_path / "artifacts",
        repo_root=tmp_path / "repo",
        generated_root=tmp_path,
        config=cfg,
    )

    initial_root = rt.delegate(Task(description="root"))
    assert initial_root._safety_timeout_seconds is None  # exempted

    # A self-heal successor re-delegated at the top level (parent is None) must
    # NOT inherit the cap — this was the root cause of the "main orchestrator
    # still times out" after the first root dies and _fresh_restart() respawns it.
    successor = rt.delegate(Task(description="root successor"))
    assert successor._safety_timeout_seconds is None

    # Child agents spawned under a root still get the cap.
    child = rt.delegate(Task(description="child"), parent=initial_root)
    assert child._safety_timeout_seconds == 60.5


def test_root_timeout_when_disable_root_timeout_false(tmp_path) -> None:
    """Without disable_root_timeout, even the root agent inherits the cap."""
    cfg = HarnessConfig(safety=SafetyConfig(
        timeout_seconds=60.5,
        disable_root_timeout=False,
    ))
    rt = Runtime(
        artifact_root=tmp_path / "artifacts",
        repo_root=tmp_path / "repo",
        generated_root=tmp_path,
        config=cfg,
    )
    root = rt.delegate(Task(description="root"))
    assert root._safety_timeout_seconds == 60.5


def test_runtime_wires_recovery_from_config(tmp_path) -> None:
    cfg = HarnessConfig(safety=SafetyConfig(repeated_recovery_attempts=3))
    rt = Runtime(
        artifact_root=tmp_path / "artifacts",
        repo_root=tmp_path / "repo",
        generated_root=tmp_path,
        config=cfg,
    )
    assert rt._repeated_recovery_attempts == 3
    task = Task(description="t")
    agent = rt.delegate(task)
    assert agent._repeated_recovery_left == 3


def test_runtime_wires_call_timeout_to_agent(tmp_path) -> None:
    """llm.call_timeout_seconds is threaded from config through Runtime to each agent."""
    cfg = HarnessConfig(llm=LLMProviderConfig(call_timeout_seconds=45.5))
    rt = Runtime(
        artifact_root=tmp_path / "artifacts",
        repo_root=tmp_path / "repo",
        generated_root=tmp_path,
        config=cfg,
    )
    assert rt._call_timeout_seconds == 45.5
    root = rt.delegate(Task(description="t"))
    assert root._call_timeout_seconds == 45.5
    child = rt.delegate(Task(description="c"), parent=root)
    assert child._call_timeout_seconds == 45.5


@pytest.mark.asyncio
async def test_run_timeout_binds_mid_call(runtime: Runtime) -> None:
    """A slow LLM call must not overshoot the full-run budget: the run timeout
    is enforced even while a request is in flight."""

    class SlowLLM(LLMProvider):
        async def generate(self, system, user, config=None):
            raise NotImplementedError

        async def generate_with_tools(self, messages, tools, config=None):
            await asyncio.sleep(5)  # far longer than the run budget
            return ToolCallResponse(content="done", model="mock")

        async def generate_structured(self, system, user, response_model, config=None):
            raise NotImplementedError

    runtime.set_llm(SlowLLM())

    root = _make_agent(runtime, Task(description="slow"))
    root._started_at = time.monotonic() - 1.0  # 1s already elapsed
    root._safety_timeout_seconds = 0.5  # only 0.5s left -> must stop mid-call
    await root._run_loop()
    assert root.task.status.value == "failed"
    assert root._terminated_by_safety is True


@staticmethod
def _hang_llm(sleep: float) -> type[LLMProvider]:
    class HangingLLM(LLMProvider):
        def __init__(self):
            self.calls = 0

        async def generate(self, system, user, config=None):
            raise NotImplementedError

        async def generate_with_tools(self, messages, tools, config=None):
            self.calls += 1
            await asyncio.sleep(sleep)
            return ToolCallResponse(content="done", model="mock")

        async def generate_structured(self, system, user, response_model, config=None):
            raise NotImplementedError

    return HangingLLM


async def _run_slow_agent(runtime: Runtime, llm_cls: type[LLMProvider], *, call_timeout: float) -> Agent:
    """Run an agent whose LLM call hangs with a per-call timeout of ``call_timeout``.
    Returns the finished agent (status reflects the outcome)."""
    runtime.set_llm(llm_cls())
    root = _make_agent(runtime, Task(description="slow"))
    root._call_timeout_seconds = call_timeout
    await root.run()
    return root


@pytest.mark.asyncio
async def test_call_timeout_binds_single_hung_call(runtime: Runtime) -> None:
    """llm.call_timeout_seconds is a hard total-request deadline: a provider that
    never returns (longer than the cap) is abandoned, not awaited indefinitely."""
    # The hang (5s) far exceeds the 0.25s per-call cap.
    root = await _run_slow_agent(runtime, _hang_llm(5.0), call_timeout=0.25)
    assert root.task.status.value == "failed"
    assert "per-call" in (root.last_failure.error if root.last_failure else "")


@pytest.mark.asyncio
async def test_call_timeout_retries_then_fails(runtime: Runtime) -> None:
    """Each per-call timeout is retried (transient) and only fails after the last
    attempt, so one slow call doesn't instantly kill the agent on its first trip."""
    llm = _hang_llm(5.0)()
    runtime.set_llm(llm)
    root = _make_agent(runtime, Task(description="slow"))
    root._call_timeout_seconds = 0.25
    await root.run()
    # default max_retries=3 -> the call should have been attempted 4 times.
    assert llm.calls == 4
    assert root.task.status.value == "failed"


@pytest.mark.asyncio
async def test_call_timeout_does_not_affect_fast_calls(runtime: Runtime) -> None:
    """A fast LLM call is untouched by the per-call cap."""
    llm = _hang_llm(0.0)()
    runtime.set_llm(llm)
    root = _make_agent(runtime, Task(description="fast"))
    root._call_timeout_seconds = 0.25
    await root.run()
    assert root.task.status.value == "completed"


def test_delegate_nudge_fires_once_for_non_delegating_agent(runtime: Runtime) -> None:
    """An agent past the threshold with no delegations gets ONE reminder; once it
    has delegated (or the nudge budget is spent) no further nudge is emitted."""
    root = _make_agent(runtime, Task(description="task"))
    root._delegate_nudge_threshold = 4
    root._delegate_nudge_attempts = 1
    root._delegate_nudge_left = 1

    # Below threshold -> no nudge.
    root._iteration = 3
    root._maybe_nudge_delegation()
    assert len(root.context.messages) == 0

    # At/above threshold -> one nudge, appended (not mutated).
    root._iteration = 4
    root._maybe_nudge_delegation()
    assert len(root.context.messages) == 1
    assert root.context.messages[0]["role"] == "user"
    assert "have not delegated" in root.context.messages[0]["content"]
    budget_after = root._delegate_nudge_left

    # Budget exhausted -> no second nudge even if it keeps not delegating.
    root._iteration = 9
    root._maybe_nudge_delegation()
    assert len(root.context.messages) == 1
    assert root._delegate_nudge_left == budget_after


def test_delegate_nudge_suppressed_after_first_delegate(runtime: Runtime) -> None:
    """Once the agent has delegated, the reminder never fires."""
    root = _make_agent(runtime, Task(description="task"))
    root._delegate_nudge_threshold = 2
    root._delegate_nudge_attempts = 1
    root._delegate_nudge_left = 1
    root._has_delegated = True

    root._iteration = 20
    root._maybe_nudge_delegation()
    assert len(root.context.messages) == 0


def test_near_identical_bash_churn_warns_but_never_fails(runtime: Runtime) -> None:
    """The trace failure mode: the model re-runs a path listing with slightly
    different head/tail/sed modifiers. The near-identical notice must inject
    a bounded warning into the context and NEVER fail the run."""
    root = _make_agent(
        runtime, Task(description="audit churn"),
        repeated_call_limit=20, repeated_recovery_attempts=1,
        near_identical_threshold=3, near_identical_window=6,
        near_identical_similarity=0.6, near_identical_warning_attempts=2,
    )
    root.fail = lambda error, trace=None: root.outcome.__setattr__("failure", error)

    events: list[Any] = []
    runtime.event_bus.on_activity(lambda ev: events.append(ev))

    cmds = [
        f'cd /repo/src && find . -type f -name "*.py" | sort | head -{n}'
        for n in range(1, 31)
    ]
    for i, cmd in enumerate(cmds, start=1):
        ok = root._check_repeated_calls(ToolCallResponse(
            content=None, model="mock",
            tool_calls=[ToolCallData(id=f"c{i}", name="bash", arguments={"command": cmd})],
        ))
        # The soft warning must never stop the loop (return True would fail it).
        assert ok is False, f"near-identical warning unexpectedly stopped the loop at call {i}"

    assert root.outcome.failure is None
    assert root._repeated_calls_detected is False

    notices = [
        m for m in root.context.messages
        if m["role"] == "user" and m["content"].startswith("[notice]")
    ]
    assert notices, "expected at least one near-identical notice"
    assert len(notices) <= 2  # bounded by near_identical_warning_attempts

    near_events = [
        e for e in events if e.data.get("warning_type") == "near_identical_calls"
    ]
    assert near_events, "expected a near_identical_calls safety event"
    assert near_events[0].data["tool_name"] == "bash"
    assert near_events[-1].data["attempts_remaining"] == 0  # budget fully consumed


def test_near_identical_ignores_pure_pagination(runtime: Runtime) -> None:
    """Same command, only token_offset advancing = legit paging -> silent."""
    root = _make_agent(
        runtime, Task(description="page"), repeated_call_limit=20,
        near_identical_threshold=3, near_identical_warning_attempts=2,
    )
    root.fail = lambda error, trace=None: None
    for i in range(1, 11):
        ok = root._check_repeated_calls(ToolCallResponse(
            content=None, model="mock",
            tool_calls=[ToolCallData(
                id=f"b{i}", name="bash",
                arguments={"command": "ls -la", "token_offset": i * 100},
            )],
        ))
        assert ok is False
    assert not [m for m in root.context.messages if m["content"].startswith("[notice]")]


def test_near_identical_unmonitored_tools_silent(runtime: Runtime) -> None:
    """read is not monitored by default: reading many different (but
    textually similar) source paths is legitimate exploration, never warned."""
    root = _make_agent(runtime, Task(description="reads"),
        near_identical_threshold=3, near_identical_window=6,
        near_identical_warning_attempts=2,
    )
    paths = [
        "ma_crossover", "donchian", "bollinger", "rotation",
        "backtester", "rotation_backtester", "walkforward", "statistics",
        "continuous_optimization", "main", "config", "basket",
    ]
    for i, name in enumerate(paths, start=1):
        ok = root._check_repeated_calls(ToolCallResponse(
            content=None, model="mock",
            tool_calls=[ToolCallData(
                id=f"r{i}", name="read",
                arguments={"path": f"/8repo/src/strategy/{name}.py"},
            )],
        ))
        assert ok is False
    assert not [m for m in root.context.messages if m["content"].startswith("[notice]")]


def test_runtime_wires_near_identical_from_config(tmp_path) -> None:
    cfg = HarnessConfig(safety=SafetyConfig(
        near_identical_threshold=4,
        near_identical_window=9,
        near_identical_similarity=0.5,
        near_identical_tools=["bash", "grep"],
        near_identical_warning_attempts=7,
    ))
    rt = Runtime(
        artifact_root=tmp_path / "artifacts",
        repo_root=tmp_path / "repo",
        generated_root=tmp_path,
        config=cfg,
    )
    assert rt._near_identical_threshold == 4
    assert rt._near_identical_window == 9
    assert rt._near_identical_similarity == 0.5
    assert rt._near_identical_tools == ["bash", "grep"]
    assert rt._near_identical_warning_attempts == 7
    root = rt.delegate(Task(description="t"))
    assert root._near_identical_threshold == 4
    assert root._near_identical_window == 9
    assert root._near_identical_similarity == 0.5
    assert root._near_identical_tools == ("bash", "grep")
    assert root._near_identical_warning_left == 7

