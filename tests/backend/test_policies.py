"""Unit tests for the composable policies (core/policies/).

These exercise the extracted decision components directly — without a
Runtime or Agent — proving they are the standalone units a plugin host
(MCP server / extension) would reuse.
"""

from __future__ import annotations

from pathlib import Path

from dynamic_harness.core.policies.agent import AgentPolicy
from dynamic_harness.core.policies.budget import BudgetPolicy, BudgetVerdict, TimeoutPolicy, TokenBudgetPolicy
from dynamic_harness.core.policies.context import ContextMetricPolicy
from dynamic_harness.core.policies.cost import CostPolicy
from dynamic_harness.core.policies.disclosure import DisclosurePolicy
from dynamic_harness.core.policies.filesystem import SandboxPolicy
from dynamic_harness.core.policies.heal import HealBudget, HealPolicy, ResumePlanner
from dynamic_harness.core.policies.loop_guard import (
    LoopGuard,
    bash_family,
    bash_read_regions,
    normalize_tool_signature,
    paginationless_signature,
    regions_overlap,
)
from dynamic_harness.core.policies.network import WebFetchPolicy
from dynamic_harness.core.policies.nudge import NudgePolicy
from dynamic_harness.core.policies.permissions import ToolPermissionPolicy
from dynamic_harness.core.policies.process import BashSafetyPolicy
from dynamic_harness.core.policies.result_cache import ResultCachePolicy
from dynamic_harness.core.policies.retry import RetryPolicy
from dynamic_harness.core.policies.spawn import SpawnPolicy
from dynamic_harness.core.policies.verify import VerifyPolicy, VerifyResult
from dynamic_harness.core.result_store import ResultStore
from dynamic_harness.core.task import TaskStatus


# -- LoopGuard ---------------------------------------------------------


class _Call:
    def __init__(self, name: str, arguments: dict):
        self.name = name
        self.arguments = arguments


def _batch(guard: LoopGuard, names: list[str], content: str | None = None):
    """Feed one turn to the guard; return the (first) action or None."""
    actions = guard.check([_Call(n, {}) for n in names], content=content)
    return actions[0] if actions else None


def test_loop_guard_clean_turn_no_action() -> None:
    guard = LoopGuard(repeated_call_limit=3, repeated_recovery_attempts=0)
    assert _batch(guard, ["read", "bash"]) is None


def test_loop_guard_identical_batch_nudges_then_fails() -> None:
    guard = LoopGuard(repeated_call_limit=3, repeated_recovery_attempts=1)
    first = _batch(guard, ["status"])
    assert first is None  # pure-monitoring turn: never counted
    first = _batch(guard, ["bash"])
    assert first is None
    second = _batch(guard, ["bash"])
    assert second is None  # 2 < limit
    third = _batch(guard, ["bash"])
    assert third is not None
    assert third.action == "nudge"
    assert third.warning_type == "repeated_calls"
    assert "[safety] You are looping" in third.user_message
    fourth = _batch(guard, ["bash"])
    assert fourth is not None
    assert fourth.action == "fail"
    assert fourth.stop


def test_loop_guard_zero_recovery_fails_immediately() -> None:
    guard = LoopGuard(repeated_call_limit=2, repeated_recovery_attempts=0)
    _batch(guard, ["bash"])
    action = _batch(guard, ["bash"])
    assert action is not None and action.action == "fail"


def test_loop_guard_near_identical_warns_without_failing() -> None:
    guard = LoopGuard(
        repeated_call_limit=100,
        repeated_recovery_attempts=1,
        near_identical_threshold=3,
        near_identical_tools=("bash",),
        near_identical_warning_attempts=2,
    )
    # Three turns re-reading the SAME file through different wrappers.
    for cmd in (
        "sed -n '1,50p' file.txt",
        "awk 'NR>=1 && NR<=50' file.txt",
        "cat file.txt",
    ):
        guard.check([_Call("bash", {"command": cmd})])
    # 4th appearance of the same material → warning (never fails the run).
    action = guard.check([_Call("bash", {"command": "head -50 file.txt"})])
    assert action and action[0].action == "continue"
    assert action[0].warning_type == "near_identical_calls"
    assert "[notice]" in action[0].user_message
    assert not action[0].stop


def test_loop_guard_bash_family_normalizes_pagination() -> None:
    assert "range" in bash_family("sed -n '1,50p' file.py")
    assert bash_family("sed -n '1,50p' file.py") == bash_family("sed -n '1,80p' file.py")
    assert bash_family("head -50 file.py") == bash_family("head -100 file.py")
    assert bash_family("cat a.py") != bash_family("cat b.py")


def test_loop_guard_read_regions_detect_overlap() -> None:
    a = bash_read_regions("sed -n '1,50p' src/x.py")
    b = bash_read_regions("awk 'NR>=40 && NR<=90' src/x.py")
    assert b and regions_overlap(a, b)
    c = bash_read_regions("sed -n '60,100p' src/x.py")
    assert not regions_overlap(a, c)  # disjoint forward paging = progress


def test_loop_guard_signatures_are_whitespace_insensitive() -> None:
    assert normalize_tool_signature("read", {"path": " A.PY  "}) == normalize_tool_signature(
        "read", {"path": "a.py"}
    )
    assert paginationless_signature("read", {"path": "x", "token_offset": 10}) == (
        paginationless_signature("read", {"path": "x", "token_offset": 20})
    )


def test_loop_guard_clear_drops_state() -> None:
    guard = LoopGuard(repeated_call_limit=2, repeated_recovery_attempts=0)
    guard.check([_Call("bash", {})])
    guard.check([_Call("bash", {})])
    assert guard.repeated_calls_detected is True
    guard.clear()
    assert len(guard.recent_batches) == 0
    assert guard.recent_near_identical.maxlen == guard.near_identical_window


# -- ResultCachePolicy -------------------------------------------------


def test_result_cache_mutators_never_snapshotted() -> None:
    pol = ResultCachePolicy()
    assert not pol.is_cacheable("write")
    assert not pol.is_cacheable("delegate")
    assert not pol.is_cacheable("result_read")
    assert pol.is_cacheable("read")
    assert pol.is_cacheable("bash")


def test_result_cache_snapshot_returns_handle_or_none() -> None:
    pol = ResultCachePolicy()
    store = ResultStore(max_entries=4)
    handle = pol.snapshot(store, "read", "full output")
    assert handle is not None and store.get(handle) == "full output"
    assert pol.snapshot(store, "write", "x") is None


def test_result_cache_render_truncates_and_advertises_handle() -> None:
    pol = ResultCachePolicy()
    body = "A" * 500
    out = pol.render(body, token_limit=10, token_offset=0, name="read", result_id="abc")
    assert out.startswith("A" * 40)
    assert 'result_read(result_id="abc"' in out
    assert "A" * 40 in out and body[40:] not in out


def test_result_cache_render_offset_beyond() -> None:
    pol = ResultCachePolicy()
    out = pol.render("short", token_limit=10, token_offset=100, name="read", result_id="abc")
    assert "offset beyond content length" in out
    assert "result_id=abc" in out
    no_handle = pol.render("short", token_limit=10, token_offset=100, name="git", result_id=None)
    assert no_handle == "(offset beyond content length)"


# -- SpawnPolicy -------------------------------------------------------


def test_spawn_policy_caps_have_order_and_messages() -> None:
    pol = SpawnPolicy(max_agents=3, max_depth=2, max_same_target=2)
    assert pol.check(agents_spawned=3, depth=0).allowed is False
    assert pol.check(agents_spawned=2, depth=0).allowed is True
    assert pol.check(agents_spawned=2, depth=3).allowed is False
    assert pol.check(agents_spawned=2, depth=1, same_target_count=2).allowed is False
    assert "target delegation limit reached" in (
        pol.check(agents_spawned=2, depth=1, same_target_count=2,
                  same_target_signature="src/foo.py").reason or ""
    )
    assert pol.check(agents_spawned=2, depth=1, same_target_count=1).allowed is True


def test_spawn_policy_none_disables_cap() -> None:
    pol = SpawnPolicy(max_agents=None, max_depth=None, max_same_target=None)
    assert pol.check(agents_spawned=9999, depth=9999, same_target_count=9999).allowed


def test_spawn_policy_budget_line_and_warnings() -> None:
    pol = SpawnPolicy(max_agents=10, max_depth=5, max_same_target=4)
    usage = {
        "agents": 3, "max_agents": 10,
        "depth": 2, "max_depth": 5,
        "max_same_target": 4,
        "top_same_targets": [{"target": "src/", "count": 2}],
    }
    line = pol.budget_line(usage)
    assert "[delegation budget]" in line
    assert "agents 3/10" in line
    assert pol.near_cap_warnings({**usage, "agents": 8}, depth=2) == ["total agents 8/10"]
    assert pol.near_cap_note(["total agents 8/10"]).startswith("You are approaching")


# -- HealBudget / HealPolicy -------------------------------------------


def test_heal_budget_shared_counters() -> None:
    b = HealBudget()
    assert b.can("resume", 1)
    assert b.bump("resume") == 1
    assert not b.can("resume", 1)
    assert b.can("fresh", 1)
    assert b["resume"] == 1
    assert b.as_dict() == {"resume": 1, "fresh": 0}


def test_heal_policy_diagnosis() -> None:
    assert HealPolicy.diagnose(True) == "rot"
    assert HealPolicy.diagnose(False) == "blunt"
    assert HealPolicy.diagnose_for_status(TaskStatus.completed, True, False) == "none"
    assert HealPolicy.diagnose_for_status(TaskStatus.failed, True, False) == "blunt"
    assert HealPolicy.diagnose_for_status(TaskStatus.completed, False, True) == "rot"


def test_heal_policy_deliverable_gate(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    assert HealPolicy.deliverable_ok([str(target)], None, None) is False
    target.write_text("x")
    assert HealPolicy.deliverable_ok([str(target)], None, None) is True
    # Prose-only report (no files, no artifacts) is NOT a deliverable.
    assert HealPolicy.deliverable_ok(None, None, None) is False
    assert HealPolicy.deliverable_ok(None, [], ["a.md"]) is True
    assert HealPolicy.deliverable_ok(None, ["art1"], None) is True


def test_heal_policy_wordings() -> None:
    nudge = HealPolicy.resume_nudge([], None)
    assert "did not write a deliverable" in nudge
    nudge = HealPolicy.resume_nudge(["out.txt"], None)
    assert "out.txt" in nudge
    nudge = HealPolicy.resume_nudge(None, "boom")
    assert "failed with: boom" in nudge
    fresh = HealPolicy.fresh_restart_note("boom", None, note="retry carefully")
    assert "prior attempt failed — boom" in fresh
    assert "Parent instruction: retry carefully" in fresh
    assert "writing" in HealPolicy.fresh_restart_note(None, ["out.txt"], None)

def test_heal_policy_and_spawn_policy_hold_limits() -> None:
    heal = HealPolicy(max_resumes=3, max_fresh=2)
    assert heal.max_resumes == 3
    assert heal.max_fresh == 2
    spawn = SpawnPolicy(max_agents=1, max_depth=2, max_same_target=3, warning_attempts=4)
    assert spawn.max_agents == 1
    assert spawn.max_depth == 2
    assert spawn.max_same_target == 3
    assert spawn.warning_attempts == 4

# -- RetryPolicy ---------------------------------------------------------


class _Exc(Exception):
    pass

class _Resp:
    def __init__(self, headers=None) -> None:
        self.headers = headers or {}


class _DuckRateLimit(Exception):
    """429 with a Retry-After header, for the header-parsing tests."""

    def __init__(self, retry_after: str | None = None) -> None:
        super().__init__("boom")
        self.response = _Resp({"retry-after": retry_after} if retry_after else {})


def test_retry_classification() -> None:
    from openai import APITimeoutError, APIStatusError, RateLimitError
    import httpx

    request = httpx.Request("POST", "http://provider.invalid/v1/chat/completions")
    rl = RateLimitError(
        message="429", response=httpx.Response(429, request=request), body=None
    )
    status_err = APIStatusError(
        message="server error",
        response=httpx.Response(503, request=request),
        body=None,
    )
    assert RetryPolicy.is_rate_limit(rl) is True
    assert RetryPolicy.is_rate_limit(ValueError("engine_overloaded")) is True
    assert RetryPolicy.is_rate_limit(ValueError("429 too many requests")) is True
    assert RetryPolicy.is_rate_limit(ValueError("method not allowed")) is False
    assert RetryPolicy.is_retryable(APITimeoutError(request=request)) is True
    assert RetryPolicy.is_retryable(status_err) is True
    assert RetryPolicy.is_retryable(ValueError("timeout")) is True
    assert RetryPolicy.is_retryable(ValueError("bad request")) is False


def test_retry_delay_formula_and_budgets() -> None:
    pol = RetryPolicy(
        retry_max_attempts=4, rate_limit_max_attempts=6,
        retry_base_delay_seconds=1.0, retry_max_delay_seconds=7.0,
        retry_jitter_seconds=0.0, rate_limit_backoff_multiplier=3.0,
    )
    assert pol.worst_budget == 6
    assert pol.delay_seconds(rate_limited=True, retry_count=1) == 3.0
    assert pol.delay_seconds(rate_limited=True, retry_count=2) == 6.0
    assert pol.delay_seconds(rate_limited=True, retry_count=3) == 7.0  # capped
    assert pol.delay_seconds(rate_limited=False, retry_count=1) == 1.0
    # Retry-After extends the backoff when longer.
    assert pol.delay_seconds(rate_limited=True, retry_count=1, retry_after=25.0) == 7.0
    assert pol.delay_seconds(
        rate_limited=True, retry_count=1, retry_after=4.0
    ) == 4.0


def test_retry_drop_session_pin() -> None:
    pol = RetryPolicy(fallback_on_rate_limit=True)
    assert pol.should_drop_session_pin(rate_limited=True, has_session_id=True) is True
    assert pol.should_drop_session_pin(rate_limited=True, has_session_id=False) is False
    assert pol.should_drop_session_pin(rate_limited=False, has_session_id=True) is False
    pol2 = RetryPolicy(fallback_on_rate_limit=False)
    assert pol2.should_drop_session_pin(rate_limited=True, has_session_id=True) is False


def test_retry_after_header() -> None:
    assert RetryPolicy.retry_after_seconds(_DuckRateLimit("12")) == 12.0
    assert RetryPolicy.retry_after_seconds(ValueError("no response")) is None
    assert RetryPolicy.retry_after_seconds(_DuckRateLimit()) is None


# -- DisclosurePolicy ----------------------------------------------------


def test_disclosure_views_from_report() -> None:
    v = DisclosurePolicy.views_from_report("Line one\nLine two", technical="T", full_report="F")
    assert v["headline"] == "Line one"
    assert v["summary_200"] == "Line one\nLine two"
    assert v["summary_1000"] == ""
    assert v["technical"] == "T"
    assert v["full_report"] == "F"
    long = "x" * 250
    v = DisclosurePolicy.views_from_report(long)
    assert v["summary_200"] == "x" * 200
    assert v["summary_1000"] == "x" * 250


def test_disclosure_build_view_dict_matches_archive() -> None:
    v = DisclosurePolicy.build_view_dict(headline="H", summary_text="S" * 250, raw_data="RAW")
    assert v["headline"] == "H"
    assert v["summary_1000"] == "S" * 250
    assert v["raw_data"] == "RAW"


def test_disclosure_validate_level_and_reveal() -> None:
    assert DisclosurePolicy.validate_level("auto") == "auto"
    assert DisclosurePolicy.validate_level("FULL") == "full"
    assert DisclosurePolicy.validate_level("bogus") is None


# -- ResumePlanner -------------------------------------------------------


def test_resume_planner_strategy_validation() -> None:
    assert ResumePlanner.validate(None) == ("automatic", None)
    assert ResumePlanner.validate("fresh") == ("fresh", None)
    norm, err = ResumePlanner.validate("bogus")
    assert norm is None and err is not None
    assert "One of" in err


def test_resume_planner_refusal_and_layers() -> None:
    assert "rotted" in ResumePlanner.refusal_for_rot("resume", "rot")
    assert ResumePlanner.refusal_for_rot("automatic", "rot") is None
    assert ResumePlanner.should_attempt_resume("automatic", "blunt") is True
    assert ResumePlanner.should_attempt_resume("automatic", "rot") is False
    assert ResumePlanner.should_attempt_resume("fresh", "blunt") is False
    assert ResumePlanner.should_attempt_fresh("automatic", healed=False) is True
    assert ResumePlanner.should_attempt_fresh("automatic", healed=True) is False
    assert ResumePlanner.should_attempt_fresh("resume", healed=False) is False


# -- AgentPolicy ---------------------------------------------------------


def test_agent_policy_from_config_defaults_match_no_config() -> None:
    from dynamic_harness.config import HarnessConfig

    a = AgentPolicy.from_config(None)
    b = AgentPolicy.from_config(HarnessConfig())
    assert a.safety_max_iterations == b.safety_max_iterations == 400
    assert a.max_agent_tokens is None and b.max_agent_tokens is None
    assert a.call_timeout_seconds == b.call_timeout_seconds == 500.0
    assert a.safety_timeout_seconds == b.safety_timeout_seconds == 7200.0
    assert a.disable_root_timeout is True and b.disable_root_timeout is True


def test_agent_policy_root_timeout_exemption() -> None:
    a = AgentPolicy(safety_timeout_seconds=60.5, disable_root_timeout=True)
    assert a.root_timeout() is None
    assert a.child_timeout() == 60.5
    b = AgentPolicy(safety_timeout_seconds=60.5, disable_root_timeout=False)
    assert b.root_timeout() == 60.5


# -- CostPolicy (G9) ------------------------------------------------------


def test_cost_policy_conversion() -> None:
    pol = CostPolicy(price_input_per_mtok=0.1, price_output_per_mtok=0.3)
    assert abs(pol.cost(tokens_in=1000, tokens_out=1000) - 0.0004) < 1e-9
    assert abs(pol.cost(tokens_in=0, tokens_out=1_000_000) - 0.3) < 1e-9
    assert abs(pol.input_cost(1_000_000) - 0.1) < 1e-9
    assert CostPolicy().cost(tokens_in=1000, tokens_out=0) == 0.0


# -- BudgetPolicy (G8) ----------------------------------------------------


def test_budget_policy_grants_within_cap() -> None:
    pol = BudgetPolicy(max_agent_tokens=1000)
    v = pol.check(current=100, requested=300, reason="need more context")
    assert isinstance(v, BudgetVerdict)
    assert v.allowed and v.remaining == 900
    assert "approved" in v.message


def test_budget_policy_denies_beyond_cap() -> None:
    pol = BudgetPolicy(max_agent_tokens=1000)
    v = pol.check(current=900, requested=300, reason="more context")
    assert not v.allowed
    assert v.remaining == 100
    assert "would exceed" in v.message


def test_budget_policy_uncapped() -> None:
    pol = BudgetPolicy(max_agent_tokens=None)
    v = pol.check(current=10_000, requested=400, reason="x")
    assert v.allowed


# -- VerifyPolicy (G1) ----------------------------------------------------


def test_verify_policy_acceptance_matching() -> None:
    pol = VerifyPolicy()
    v = pol.check(body="Covered both the API surface and the memory layout.", acceptance=["API", "memory"])
    assert isinstance(v, VerifyResult)
    assert v.met
    assert v.missing_terms == []
    v2 = pol.check(body="Only the API surface is covered.", acceptance=["API", "lambda calculus"])
    assert not v2.met
    assert v2.missing_terms == ["lambda calculus"]


def test_verify_policy_no_acceptance_passes() -> None:
    pol = VerifyPolicy()
    v = pol.check(body="Anything", acceptance=[])
    assert v.met


def test_verify_policy_guidance() -> None:
    v = VerifyPolicy().check(
        body="we covered the core cache.", acceptance=["cache", "eviction"]
    )
    assert "eviction" in v.message

# -- TimeoutPolicy / TokenBudgetPolicy --------------------------------------


def test_timeout_policy_remaining_and_messages() -> None:
    pol = TimeoutPolicy(timeout_seconds=60.0)
    assert pol.enabled and pol.remaining_seconds(10) == 50.0
    assert pol.remaining_seconds(70) == 0.0
    assert pol.exceeded(70) is True and pol.exceeded(10) is False
    assert pol.timeout_message(60.0, 5) == "Agent timed out after 60.0s (5 iterations)"
    assert "exceeded the budget" in pol.timeout_message(60.0, 5, mid_call=True)
    uncapped = TimeoutPolicy(timeout_seconds=None)
    assert not uncapped.enabled and uncapped.remaining_seconds(9) is None


def test_token_budget_policy() -> None:
    pol = TokenBudgetPolicy(max_agent_tokens=1000)
    assert pol.exceeded(1001) is True and pol.exceeded(999) is False
    assert "1001 > 1000" in pol.exceed_message(1001)
    assert pol.budget_guidance() and "at most 1000 total tokens" in pol.budget_guidance()
    assert TokenBudgetPolicy(max_agent_tokens=None).budget_guidance() is None


# -- ToolPermissionPolicy ---------------------------------------------------


def test_tool_permission_role_gating() -> None:
    assert ToolPermissionPolicy.tool_allowed("orchestrator", "delegate") is True
    assert ToolPermissionPolicy.tool_allowed("orchestrator", "read") is False
    assert ToolPermissionPolicy.tool_allowed(None, "read") is True
    msg = ToolPermissionPolicy.role_refusal("orchestrator", "read")
    assert msg is not None and "Delegate this work instead" in msg
    assert ToolPermissionPolicy.role_refusal("orchestrator", "delegate") is None


def test_tool_permission_eligibility() -> None:
    from dynamic_harness.core.task import TaskStatus

    assert ToolPermissionPolicy.killable(TaskStatus.running) is True
    assert ToolPermissionPolicy.killable(TaskStatus.completed) is False
    assert ToolPermissionPolicy.conversable(TaskStatus.completed) is True
    assert ToolPermissionPolicy.conversable(TaskStatus.failed) is False
    assert ToolPermissionPolicy.resumable(TaskStatus.failed) is True


# -- BashSafetyPolicy -------------------------------------------------------


def test_bash_safety_read_only_and_shell() -> None:
    assert BashSafetyPolicy.is_read_only(["ls", "-la"]) is True
    assert BashSafetyPolicy.is_read_only(["git", "status"]) is True
    assert BashSafetyPolicy.is_read_only(["git", "commit", "-m", "x"]) is False
    assert BashSafetyPolicy.is_read_only(["rm", "x"]) is False
    assert BashSafetyPolicy.needs_shell("cd /x && ls") is True
    assert BashSafetyPolicy.needs_shell("ls -la") is False
    cmd, wd = BashSafetyPolicy.resolve_workdir("cd /tmp && ls", None)
    assert cmd == "ls" and wd == "/tmp"
    cmd, wd = BashSafetyPolicy.resolve_workdir("ls", "/cwd")
    assert cmd == "ls" and wd == "/cwd"


# -- WebFetchPolicy ---------------------------------------------------------


def test_webfetch_policy_rejects_restricted_and_validates() -> None:
    pol = WebFetchPolicy()
    assert pol.validate("http://127.0.0.1/x") is not None
    assert pol.validate("http://10.0.0.1/x") is not None
    assert pol.validate("ftp://example.com/x") is not None
    assert pol.validate("not a url") is not None
    assert pol.validate("https://example.com/x") is None
    assert "TRUNCATED" in pol.truncation_note(300_000)
    assert "too many redirects" in pol.too_many_redirects_message()


# -- SandboxPolicy ----------------------------------------------------------


def test_sandbox_policy_containment(tmp_path) -> None:
    root = tmp_path / "ws"
    root.mkdir()
    pol = SandboxPolicy(root=root)
    inside = pol.resolve_safe_path("sub/file.txt")
    assert inside == (root / "sub/file.txt").resolve()
    try:
        pol.resolve_safe_path("../escape.txt")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
    assert SandboxPolicy.is_hidden(".git") is True
    assert SandboxPolicy.is_hidden("src/main.py") is False


# -- ContextMetricPolicy ----------------------------------------------------


def test_context_metric_policy() -> None:
    assert ContextMetricPolicy.estimate_tokens("") == 0
    assert ContextMetricPolicy.estimate_tokens(None) == 0
    assert ContextMetricPolicy.estimate_tokens("word") == 1
    assert "after 2 attempts" in ContextMetricPolicy.compress_failure_message(ValueError("x"))


# -- NudgePolicy ------------------------------------------------------------


def test_nudge_policy_delegate_rarity() -> None:
    pol = NudgePolicy(delegate_nudge_threshold=8, delegate_nudge_attempts=1)
    assert pol.delegate_nudge(iteration=3, attempts_left=1, has_delegated=False).fire is False
    assert pol.delegate_nudge(iteration=9, attempts_left=1, has_delegated=True).fire is False
    d = pol.delegate_nudge(iteration=9, attempts_left=1, has_delegated=False)
    assert d.fire and "9 turns" in d.note
    assert d.data["attempts_remaining"] == 0
    assert pol.delegate_nudge(iteration=12, attempts_left=0, has_delegated=False).fire is False


def test_nudge_policy_iteration_warning() -> None:
    pol = NudgePolicy(iteration_warning_margin=10, iteration_warning_attempts=1, safety_max_iterations=100)
    assert pol.iteration_warning(iteration=5, attempts_left=1).fire is False
    d = pol.iteration_warning(iteration=95, attempts_left=1)
    assert d.fire and d.data["remaining"] == 5
    assert pol.iteration_warning(iteration=96, attempts_left=0).fire is False
