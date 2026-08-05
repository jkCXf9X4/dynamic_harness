"""Benchmark tasks with failable, ground-truth verifiers.

Unlike the original flow (where "success" was just agent-report completed and a
non-empty artifact), each task here carries a deterministic verifier that can
actually *fail* a run by comparing against computed ground truth. This gives the
optimization loop statistical power.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


_IGNORE_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".optimize_benchmarks", "build", "dist", ".mypy_cache", ".pytest_cache",
    ".dynamic-harness",
}


def _iter_python_files(root: Path):
    for p in sorted(root.rglob("*.py")):
        if any(part in _IGNORE_DIRS for part in p.parts):
            continue
        yield p


def _py_files_by_size(root: Path, top_n: int = 3) -> list[tuple[str, int]]:
    """Ground truth: the largest N .py files by byte size, descending."""
    files = [(str(p.relative_to(root)), p.stat().st_size) for p in _iter_python_files(root)]
    files.sort(key=lambda t: -t[1])
    return files[:top_n]


def _parse_largest_file(out: Path) -> set[tuple[str, int]]:
    """Parse the agent-produced largest-files report into (path, size) tuples."""
    if not out.exists():
        return set()
    parsed: set[tuple[str, int]] = set()
    for line in out.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = re.split(r"\s+", line)
        for tok in parts:
            m = re.match(r"(\d+)", tok)
            if m:
                size = int(m.group(0))
                # remaining tokens (minus the size) form the path
                path = " ".join(t for t in parts if t != tok).strip()
                if path:
                    parsed.add((path.replace("./", ""), size))
                break
    return parsed


@dataclass
class BenchmarkTask:
    id: str
    description: str
    artifact_paths: list[str]

    def verify(self, output_dir: Path, scan_root: Path) -> tuple[bool, str]:
        """Return (correct, note). MUST be falsifiable."""
        raise NotImplementedError


class LargestFilesTask(BenchmarkTask):
    def __init__(self) -> None:
        super().__init__(
            id="discovery",
            description=(
                "Find the 3 largest Python files in the current directory. "
                "Write the results (paths with sizes, sorted descending) to "
                ".optimize_benchmarks/largest_files.txt and report with that "
                "artifact. .optimize_benchmarks/ already exists."
            ),
            artifact_paths=[".optimize_benchmarks/largest_files.txt"],
        )

    def verify(self, output_dir: Path, scan_root: Path) -> tuple[bool, str]:
        truth = _py_files_by_size(scan_root, top_n=3)
        produced = _parse_largest_file(output_dir / "largest_files.txt")

        if not produced:
            return False, "artifact missing or unparseable"

        truth_paths = {t[0] for t in truth}
        produced_paths = {p for p, _ in produced}

        if truth_paths != produced_paths:
            missing = truth_paths - produced_paths
            extra = produced_paths - truth_paths
            return False, f"mismatch: missing={sorted(missing)} extra={sorted(extra)}"

        return True, f"top-3 match: {sorted(truth_paths)}"


class FibonacciTask(BenchmarkTask):
    def __init__(self) -> None:
        super().__init__(
            id="codegen",
            description=(
                "Write a Python function fibonacci(n) that returns the nth "
                "Fibonacci number using iteration (not recursion). Write "
                "assertion-based tests (not pytest) testing fibonacci(0)=0, "
                "fibonacci(1)=1, fibonacci(10)=55, fibonacci(20)=6765. Write to "
                ".optimize_benchmarks/fibonacci.py and "
                ".optimize_benchmarks/test_fibonacci.py. Run with python3 and "
                "confirm pass. pytest NOT available — use assert statements. "
                ".optimize_benchmarks/ exists."
            ),
            artifact_paths=[".optimize_benchmarks/fibonacci.py",
                            ".optimize_benchmarks/test_fibonacci.py"],
        )

    def verify(self, output_dir: Path, scan_root: Path) -> tuple[bool, str]:
        test_file = output_dir / "test_fibonacci.py"
        fib_file = output_dir / "fibonacci.py"
        if not test_file.exists() or not fib_file.exists():
            return False, "fibonacci.py and/or test_fibonacci.py missing"

        expected = {0: 0, 1: 1, 10: 55, 20: 6765}

        ns: dict = {}
        try:
            exec(compile(fib_file.read_text(), str(fib_file), "exec"), ns)
        except Exception as e:  # noqa: BLE001
            return False, f"fibonacci.py failed to import: {e}"

        fib = ns.get("fibonacci") or ns.get("fib")
        if fib is None:
            return False, "no fibonacci(n) function found"
        if not callable(fib):
            return False, "fibonacci is not callable"

        for n, want in expected.items():
            try:
                got = fib(n)
            except Exception as e:  # noqa: BLE001
                return False, f"fibonacci({n}) raised: {e}"
            if got != want:
                return False, f"fibonacci({n}) = {got}, expected {want}"

        # Also confirm the agent's own test file passes under python3.
        try:
            subprocess.run(
                ["python3", str(test_file)], cwd=str(output_dir),
                capture_output=True, timeout=60, check=True,
            )
        except subprocess.CalledProcessError as e:
            return False, f"test_fibonacci.py failed: {e.stderr.decode(errors='replace')[:200]}"
        except Exception as e:  # noqa: BLE001
            return False, f"could not run test_fibonacci.py: {e}"

        return True, "fibonacci values match ground truth and tests pass"


def _scan_todos(root: Path) -> list[tuple[str, int, str]]:
    hits: list[tuple[str, int, str]] = []
    for ext in ("*.py", "*.js", "*.ts"):
        for p in sorted(root.rglob(ext)):
            if any(part in _IGNORE_DIRS for part in p.parts):
                continue
            try:
                lines = p.read_text(errors="replace").splitlines()
            except OSError:
                continue
            for i, line in enumerate(lines, 1):
                if re.search(r"\b(TODO|FIXME)\b", line):
                    hits.append((str(p.relative_to(root)), i, line.strip()))
    return hits


def _parse_todos(out: Path) -> set[str]:
    if not out.exists():
        return set()
    found: set[str] = set()
    for line in out.read_text().splitlines():
        line = line.strip()
        if line:
            found.add(line)
    return found


class TodosTask(BenchmarkTask):
    def __init__(self) -> None:
        super().__init__(
            id="analysis",
            description=(
                "Search the current directory recursively for TODO and FIXME "
                "comments in *.py, *.js, *.ts files. Write report to "
                ".optimize_benchmarks/todos.txt with format FILE:LINE: comment "
                "text, one per line. Report with that artifact. "
                ".optimize_benchmarks/ exists."
            ),
            artifact_paths=[".optimize_benchmarks/todos.txt"],
        )

    def verify(self, output_dir: Path, scan_root: Path) -> tuple[bool, str]:
        truth = _scan_todos(scan_root)
        produced = _parse_todos(output_dir / "todos.txt")

        if not truth:
            # No TODOs exist → correct answer is an empty report (or absent file).
            return True, "no TODO/FIXME in tree; empty report is correct"

        truth_set = {
            f"{path}:{lineno}: {text}" for path, lineno, text in truth
        }
        missing = truth_set - produced
        extra = produced - truth_set
        if missing or extra:
            return False, f"mismatch: missing={len(missing)} extra={len(extra)}"

        return True, f"{len(truth)} TODO/FIXME hits match"


ALL_TASKS: list[BenchmarkTask] = [
    LargestFilesTask(),
    FibonacciTask(),
    TodosTask(),
]


def find_task(task_id: str) -> BenchmarkTask:
    for t in ALL_TASKS:
        if t.id == task_id:
            return t
    raise KeyError(f"unknown task id: {task_id}")
