"""Run a single (prompt, task) benchmark run and capture clean metrics.

The benchmark tasks are repo-realistic (they discover/analyze Python files), so
each run executes against the real working directory. The variable under test is
the *system prompt*: the task description stays constant and ``system_prompt``
differs between SEED (None → default) and variants (override text). To keep runs
comparable and free of cross-run contamination we:
  * snapshot + delete the task's expected output artifacts *before* the run,
    so each run must (re)produce them fresh; and
  * verify the artifacts immediately after the run, before the next run writes
    the same paths again.

Metrics come from a fresh Runtime per run (fresh usage counters, task graph),
so tokens/cost/turns/depth/latency are attributable to exactly this run.
"""

from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path

from ..core.runner import AgentRunner
from ..core.runtime import Runtime
from ..core.task import Task
from .metrics import MetricsCollector
from .tasks import BenchmarkTask


class BenchmarkRunError(Exception):
    pass


def stage_workspace(
    root: Path,
    *,
    copy_dirs: tuple[str, ...] = ("src", "tests", "_payload"),
    copy_files: tuple[str, ...] = ("pyproject.toml",),
) -> Path:
    """Create a controlled snapshot workspace from ``root`` for a benchmark run.

    Only select source directories/files are copied (excluded: venv, .git,
    .optimize_benchmarks, .dynamic-harness, caches). This keeps the scan scope
    stable and matches the verifiers' ground truth, which ignore those dirs.
    """
    ws = Path(tempfile.mkdtemp(prefix="bench_ws_", dir=str(root)))
    try:
        import shutil
        for d in copy_dirs:
            src = root / d
            if src.exists():
                shutil.copytree(
                    src, ws / d,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", ".mypy_cache"),
                )
        for f in copy_files:
            src = root / f
            if src.exists():
                shutil.copy2(src, ws / f)
        (ws / ".optimize_benchmarks").mkdir(parents=True, exist_ok=True)
    except Exception:
        shutil.rmtree(ws, ignore_errors=True)
        raise
    return ws


class RunOutcome:
    def __init__(self, metrics, root_agent_id: str) -> None:
        self.metrics = metrics
        self.root_agent_id = root_agent_id

    @property
    def passed(self) -> bool:
        return self.metrics.passed


def _clear_outputs(workspace: Path, task: BenchmarkTask) -> None:
    """Delete the task's expected artifact paths so each run reproduces them."""
    for rel in task.artifact_paths:
        p = workspace / rel
        if p.exists():
            p.unlink()


async def run_one(
    *,
    runtime_factory: Callable[[], Runtime],
    task: BenchmarkTask,
    prompt_id: str,
    collector: MetricsCollector,
    workspace: Path | None = None,
    system_prompt: str | None = None,
    keep_workspace: bool = False,
) -> RunOutcome:
    """Run ``task`` (task description fixed) with an optional variant system prompt.

    ``system_prompt`` None → SEED (default agent system prompt).
    ``system_prompt`` set  → variant override.

    Runs inside a staged snapshot workspace (chdir for the duration) so the
    agent's glob/grep/bash/read/write all resolve against a clean copy of the
    repo, and verifiers compare against that same snapshot.
    """
    import os

    if workspace is None:
        workspace = Path.cwd()
    started_in = Path.cwd()
    chdir_workspace = workspace.resolve() != started_in.resolve()

    _clear_outputs(workspace, task)
    if chdir_workspace:
        os.chdir(workspace)

    rt = runtime_factory()
    if rt._llm is None:
        if chdir_workspace:
            os.chdir(started_in)
        raise BenchmarkRunError("runtime has no LLM set")

    try:
        runner = AgentRunner(rt)
        t0 = time.monotonic()

        task_kwargs = {}
        if system_prompt is not None:
            task_kwargs["system_prompt"] = system_prompt
        root = rt.delegate(Task(description=task.description, **task_kwargs))
        await runner.run(task.description, root_agent=root)
        latency = time.monotonic() - t0
    finally:
        if chdir_workspace:
            os.chdir(started_in)

    status = root.task.status.value if root.task.status else "unknown"

    correct, note = None, ""
    try:
        output_dir = workspace / ".optimize_benchmarks"
        correct, note = task.verify(output_dir, workspace)
    except Exception as e:  # noqa: BLE001
        correct, note = False, f"verifier error: {e}"

    metrics = collector.collect(
        rt,
        root_agent_id=root.id,
        prompt_id=prompt_id,
        task_id=task.id,
        correct=correct,
        verification_note=note,
        latency_s=latency,
        status=status,
    )
    return RunOutcome(metrics=metrics, root_agent_id=root.id)
