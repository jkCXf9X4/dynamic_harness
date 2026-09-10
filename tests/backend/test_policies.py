"""Unit tests for the composable policies (core/policies/).

These exercise the extracted decision components directly — without a
Runtime or Agent — proving they are the standalone units a plugin host
(MCP server / extension) would reuse.
"""

from __future__ import annotations

from pathlib import Path

from dynamic_harness.core.policies.heal import HealBudget, HealPolicy
from dynamic_harness.core.policies.loop_guard import (
    LoopGuard,
    bash_family,
    bash_read_regions,
    normalize_tool_signature,
    paginationless_signature,
    regions_overlap,
)
from dynamic_harness.core.policies.result_cache import ResultCachePolicy
from dynamic_harness.core.policies.spawn import SpawnPolicy
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
