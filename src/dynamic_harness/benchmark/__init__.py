"""Programmatic, metric-driven benchmark harness for system prompt optimization.

This replaces the prior LLM-orchestrated flow where the *same model* that wrote
the variants also ranked them subjectively on "quality of prose." Here:

  * the variable under test is the SYSTEM PROMPT (SEED = default, or a variant
    string), while the task description stays constant per task;
  * every (prompt, task) pair runs against the real repo with a fresh Runtime;
  * objective metrics (tokens, cost, turns, depth, latency, retries) are
    captured per run; and
  * each run is verified against a failable ground-truth verifier.

Ranking is a deterministic weighted rubric (see scoring.py) grounded in data,
not authorial opinion.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from ..core.runtime import Runtime
from .metrics import MetricsCollector, RunMetrics
from .report import write_markdown, write_metrics_json
from .runner import run_one, stage_workspace
from .scoring import PromptResult, aggregate, rank
from .tasks import ALL_TASKS


class Benchmark:
    def __init__(
        self,
        *,
        runtime_factory: Callable[[], Runtime],
        output_dir: Path,
        price_input_per_mtok: float = 0.0,
        price_output_per_mtok: float = 0.0,
        collector: MetricsCollector | None = None,
    ) -> None:
        self.runtime_factory = runtime_factory
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.price_in = price_input_per_mtok
        self.price_out = price_output_per_mtok
        self.collector = collector or MetricsCollector(
            price_input_per_mtok=self.price_in,
            price_output_per_mtok=self.price_out,
        )

    async def run_prompt(
        self,
        prompt_id: str,
        *,
        system_prompt: str | None = None,
        workspace: Path | None = None,
        progress: Callable[[str], None] | None = None,
    ) -> list[RunMetrics]:
        """Run every benchmark task against one system prompt; return metrics."""
        runs: list[RunMetrics] = []
        for task in ALL_TASKS:
            if progress:
                progress(f"  [{prompt_id}] task={task.id} starting")
            outcome = await run_one(
                runtime_factory=self.runtime_factory,
                task=task,
                prompt_id=prompt_id,
                collector=self.collector,
                workspace=workspace,
                system_prompt=system_prompt,
            )
            runs.append(outcome.metrics)
            if progress:
                m = outcome.metrics
                verdict = "PASS" if outcome.passed else "FAIL"
                progress(
                    f"  [{prompt_id}] task={task.id} {verdict} "
                    f"tokens={m.total_tokens} cost={m.cost_usd:.4f} "
                    f"turns={m.total_turns} depth={m.max_depth} lat={m.latency_s:.1f}s"
                )
        return runs

    async def evaluate(
        self,
        prompts: dict[str, str | None],
        *,
        workspace: Path | None = None,
        progress: Callable[[str], None] | None = None,
        report_stem: str = "metrics",
        keep_workspace: bool = False,
    ) -> list[PromptResult]:
        """Run all prompts against all tasks and rank them on data.

        ``prompts`` maps prompt_id -> system_prompt text. A value of ``None``
        means "SEED" (use the default agent system prompt).

        A snapshot workspace is staged once (unless ``workspace`` is given) so
        every prompt/task runs against identical inputs.
        """
        owned_ws: Path | None = None
        try:
            if workspace is None:
                owned_ws = stage_workspace(Path.cwd())
                workspace = owned_ws

            all_runs: list[RunMetrics] = []
            prompt_results: list[PromptResult] = []

            for prompt_id, system_prompt in prompts.items():
                runs = await self.run_prompt(
                    prompt_id,
                    system_prompt=system_prompt,
                    workspace=workspace,
                    progress=progress,
                )
                all_runs.extend(runs)
                prompt_results.append(aggregate(prompt_id, runs))

            ranked = rank(prompt_results)

            write_metrics_json(all_runs, self.output_dir / f"{report_stem}.json")
            write_markdown(all_runs, ranked, self.output_dir / f"{report_stem}.md")
            return ranked
        finally:
            if owned_ws is not None and not keep_workspace:
                import shutil
                shutil.rmtree(owned_ws, ignore_errors=True)
