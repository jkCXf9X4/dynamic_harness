from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from dynamic_harness.benchmark.metrics import MetricsCollector, RunMetrics
from dynamic_harness.benchmark.scoring import aggregate, rank
from dynamic_harness.benchmark.tasks import (
    FibonacciTask,
    LargestFilesTask,
    TodosTask,
)


# ── Verifiers ────────────────────────────────────────────────────────────

def _ws() -> tuple[Path, Path]:
    root = Path(tempfile.mkdtemp())
    out = root / ".optimize_benchmarks"
    out.mkdir(parents=True, exist_ok=True)
    return root, out


def test_largest_files_correct(tmp_path: Path) -> None:
    root, out = _ws()
    for name, size in (("a.py", 100), ("b.py", 200), ("c.py", 300)):
        (root / name).write_text("x" * size)
    (out / "largest_files.txt").write_text(
        "./c.py 300\n./b.py 200\n./a.py 100\n"
    )
    ok, note = LargestFilesTask().verify(out, root)
    assert ok is True
    assert "top-3" in note


def test_largest_files_fails_on_wrong_set(tmp_path: Path) -> None:
    root, out = _ws()
    for name, size in (("a.py", 100), ("b.py", 200), ("c.py", 300), ("d.py", 400)):
        (root / name).write_text("x" * size)
    (out / "largest_files.txt").write_text("./a.py 100\n./b.py 200\n./c.py 300\n")
    ok, note = LargestFilesTask().verify(out, root)
    assert ok is False
    assert "mismatch" in note


def test_largest_files_fails_when_missing(tmp_path: Path) -> None:
    root, out = _ws()
    for name, size in (("a.py", 100), ("b.py", 200), ("c.py", 300)):
        (root / name).write_text("x" * size)
    ok, note = LargestFilesTask().verify(out, root)
    assert ok is False
    assert "missing or unparseable" in note


def test_fibonacci_correct(tmp_path: Path) -> None:
    root, out = _ws()
    (out / "fibonacci.py").write_text(
        "def fibonacci(n):\n    a, b = 0, 1\n    for _ in range(n):\n"
        "        a, b = b, a + b\n    return a\n"
    )
    (out / "test_fibonacci.py").write_text(
        "from fibonacci import fibonacci\n"
        "assert fibonacci(0) == 0\nassert fibonacci(20) == 6765\nprint('ok')\n"
    )
    ok, note = FibonacciTask().verify(out, root)
    assert ok is True


def test_fibonacci_wrong_value(tmp_path: Path) -> None:
    root, out = _ws()
    (out / "fibonacci.py").write_text("def fibonacci(n): return n\n")
    (out / "test_fibonacci.py").write_text("from fibonacci import fibonacci\n")
    ok, note = FibonacciTask().verify(out, root)
    assert ok is False
    assert "expected 55" in note


def test_fibonacci_missing_files(tmp_path: Path) -> None:
    root, out = _ws()
    ok, note = FibonacciTask().verify(out, root)
    assert ok is False
    assert "missing" in note


def test_todos_empty_tree_is_correct(tmp_path: Path) -> None:
    root, out = _ws()
    (out / "todos.txt").write_text("")  # nothing to find -> empty is correct
    ok, _ = TodosTask().verify(out, root)
    assert ok is True


def test_todos_matches_ground_truth(tmp_path: Path) -> None:
    root, out = _ws()
    (root / "x.py").write_text("# TODO: fix this\n# FIXME: bug\n")
    (out / "todos.txt").write_text(
        "x.py:1: # TODO: fix this\nx.py:2: # FIXME: bug\n"
    )
    ok, note = TodosTask().verify(out, root)
    assert ok is True
    assert "2 TODO/FIXME" in note


def test_todos_missing_hit_fails(tmp_path: Path) -> None:
    root, out = _ws()
    (root / "x.py").write_text("# TODO: fix this\n")
    (out / "todos.txt").write_text("")  # agent missed it
    ok, _ = TodosTask().verify(out, root)
    assert ok is False


# ── Metrics ──────────────────────────────────────────────────────────────

def _mk(pid: str, correct: bool | None, status: str = "completed", **kw) -> RunMetrics:
    base = dict(
        prompt_id=pid, task_id="t", status=status, correct=correct,
        total_tokens=5000, prompt_tokens=4000, completion_tokens=1000,
        cost_usd=0.1, agent_count=2, max_depth=1, delegations=1,
        message_count=20, total_turns=5, llm_retries=0, failures=0,
        escalations=0, latency_s=10.0,
    )
    base.update(kw)
    return RunMetrics(**base)


def test_metrics_collector_from_runtime(runtime) -> None:
    # A real Runtime with no agents -> root-only metrics.
    collector = MetricsCollector()
    m = collector.collect(
        runtime, root_agent_id="x", prompt_id="seed", task_id="t",
        correct=True, latency_s=1.0, status="completed",
    )
    assert m.agent_count == 0  # no agents registered yet
    assert m.delegations == 0
    assert m.correct is True


def test_aggregate_and_rank_orders_by_score() -> None:
    # v1 is fully correct and cheaper; seed is cheaper but less correct.
    seed = [
        _mk("seed", True, total_tokens=5000, cost_usd=0.1, total_turns=10, max_depth=2, latency_s=30),
        _mk("seed", True, total_tokens=7000, cost_usd=0.2, total_turns=12, max_depth=2, latency_s=40),
        _mk("seed", False, total_tokens=9000, cost_usd=0.3, total_turns=14, max_depth=2, latency_s=50),
    ]
    v1 = [
        _mk("v1", True, total_tokens=2000, cost_usd=0.04, total_turns=4, max_depth=1, latency_s=8),
        _mk("v1", True, total_tokens=2500, cost_usd=0.05, total_turns=5, max_depth=1, latency_s=9),
        _mk("v1", True, total_tokens=3000, cost_usd=0.06, total_turns=6, max_depth=1, latency_s=10),
    ]
    ranked = rank([aggregate("v1", v1), aggregate("seed", seed)])
    assert ranked[0].prompt_id == "v1"
    assert ranked[0].tasks_passed == 3
    assert ranked[1].tasks_passed == 2


def test_rank_ties_efficiency_among_equal_correctness() -> None:
    a = [_mk("a", True, total_tokens=1000, cost_usd=0.01, total_turns=2, max_depth=0, latency_s=2)]
    b = [_mk("b", True, total_tokens=5000, cost_usd=0.5, total_turns=10, max_depth=2, latency_s=20)]
    ranked = rank([aggregate("a", a), aggregate("b", b)])
    assert ranked[0].prompt_id == "a"  # same correctness, cheaper -> wins


def test_passed_property() -> None:
    assert _mk("p", True, status="completed").passed is True
    assert _mk("p", False, status="completed").passed is False
    assert _mk("p", True, status="failed").passed is False
