"""P4 — run the communication comparison bed against a real LLM.

Usage (from the repo root — the snapshot workspace is staged from it):

  python -m dynamic_harness.benchmark.run_comms --smoke
  python -m dynamic_harness.benchmark.run_comms                       # all cells, both tasks
  python -m dynamic_harness.benchmark.run_comms --cells off,shared,topics_parent
  python -m dynamic_harness.benchmark.run_comms --tasks interdependent --replicates 2

Each cell is one ``communication.topology`` value; everything else (task, LLM,
workspace snapshot) is identical. Runs that do not complete cleanly (provider
stalls, internal errors) are re-attempted ``--retries`` times. Results are
written as a markdown report + raw metrics JSON under the experiment directory
(``breakdown/verification/communication-structures/``).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from ..config import load_harness_config, merge_api_key
from ..llm.openai_provider import OpenAIProvider
from .comms import CELLS, COLLAB_TASKS, runtime_factory_for
from .metrics import MetricsCollector, RunMetrics
from .runner import run_one

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = REPO_ROOT / "breakdown" / "verification" / "communication-structures"


def _stage_workspace() -> Path:
    """Minimal collab snapshot: resources/ + .optimize_benchmarks/, in /tmp."""
    ws = Path(tempfile.mkdtemp(prefix="comms_ws_"))
    shutil.copytree(
        REPO_ROOT / "resources",
        ws / "resources",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    (ws / ".optimize_benchmarks").mkdir()
    return ws


def _make_llm(config, api_key: str) -> OpenAIProvider:
    return OpenAIProvider(
        model=config.llm.model,
        base_url=config.llm.base_url,
        api_key=api_key,
        verify_ssl=config.llm.verify_ssl,
        provider_ignore=config.llm.provider_ignore or None,
        provider_allow_fallbacks=config.llm.provider_allow_fallbacks,
        provider_force=config.llm.provider_force,
        timeout=config.llm.call_timeout_seconds,
    )


def _cell_of(m: RunMetrics) -> str:
    return m.prompt_id.split("#", 1)[0]


_AVG_KEYS = (
    "total_tokens", "prompt_tokens", "completion_tokens", "cost_usd",
    "latency_s", "total_turns", "message_count", "agent_count",
    "max_depth", "delegations", "llm_retries",
)


def _summarize(results: list[RunMetrics], cells: tuple[str, ...]) -> dict:
    summary: dict[str, dict] = {c: {"n": 0, "passed": 0, "correct": 0} for c in cells}
    for m in results:
        s = summary[_cell_of(m)]
        s["n"] += 1
        s["passed"] += 1 if m.passed else 0
        s["correct"] += 1 if m.correct else 0
        for key in _AVG_KEYS:
            s[key] = s.get(key, 0.0) + getattr(m, key)
        s["failures"] = s.get("failures", 0) + m.failures
        s["escalations"] = s.get("escalations", 0) + m.escalations
    for s in summary.values():
        n = max(1, s["n"])
        for key in _AVG_KEYS:
            s[key] = round(s[key] / n, 2)
    return summary


def _render_markdown(meta: dict, summary: dict, results: list[RunMetrics]) -> str:
    lines = [
        "# Communication comparison — real-LLM run",
        "",
        f"- When: `{meta['when']}`",
        f"- Model: `{meta['model']}`",
        f"- Base: `{meta['base_url']}`",
        f"- Cells: {len(summary)} · Task modes: {meta['task_ids']} · Replicates: {meta['replicates']}",
        f"- Runs: {meta['runs']} · Total cost: ${meta['total_cost']:.4f}",
        "",
        "## Per-cell summary (mean over tasks × replicates)",
        "",
        "| cell | runs | pass | correct | tokens | prompt | turns | msgs | agents | depth | fail | esc | latency s |",
        "|------|-----:|-----:|--------:|-------:|-------:|------:|-----:|-------:|------:|-----:|----:|----------:|",
    ]
    for cell, s in summary.items():
        lines.append(
            f"| {cell} | {s['n']} | {s['passed']} | {s['correct']} | "
            f"{s['total_tokens']:.0f} | {s['prompt_tokens']:.0f} | {s['total_turns']:.0f} | "
            f"{s['message_count']:.0f} | {s['agent_count']:.0f} | {s['max_depth']:.0f} | "
            f"{s['failures']} | {s['escalations']} | {s['latency_s']:.1f} |"
        )
    lines += [
        "",
        "## Per-run detail",
        "",
        "| cell | task | rep | status | correct | tokens | cost $ | turns | note |",
        "|------|------|----:|--------|--------:|-------:|-------:|------:|------|",
    ]
    for m in results:
        note = (m.verification_note or "").replace("|", "/")[:60]
        lines.append(
            f"| {_cell_of(m)} | {m.task_id} | {m.prompt_id.rsplit('rep', 1)[-1]} | "
            f"{m.status} | {m.correct} | {m.total_tokens} | {m.cost_usd:.4f} | "
            f"{m.total_turns} | {note} |"
        )
    return "\n".join(lines) + "\n"


async def _run_with_retry(
    factory, task, prompt_id, workspace, collector, retries: int, per_run_timeout_s: int,
) -> RunMetrics:
    """Run one (cell, task, rep); re-attempt when the run does not complete cleanly.

    A run counts as clean when the root ``completed`` (independent of the
    mechanical verifier — a wrong-but-completed result is a quality signal, not
    an LLM/provider flake, and is kept as-is). Only infrastructure-level
    failures (network-stalled providers, internal errors) are retried.

    ``per_run_timeout_s`` is a hard watchdog: circular blocking ``converse``
    calls can deadlock the whole agent tree (each agent awaits the other's
    loop lock), which the agent-level wall-clock does not catch because the
    loop is suspended inside a tool call. The watchdog cancels such a run and
    reports it as ``timed_out`` so the rest of the battery still completes.
    """
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            outcome = await asyncio.wait_for(
                run_one(
                    runtime_factory=factory,
                    task=task,
                    prompt_id=prompt_id,
                    collector=collector,
                    workspace=workspace,
                ),
                timeout=per_run_timeout_s,
            )
        except asyncio.TimeoutError:
            print(f"  retry[{attempt}] {prompt_id}: hit {per_run_timeout_s}s watchdog -> timeout", flush=True)
            return RunMetrics(
                prompt_id=prompt_id,
                task_id=task.id,
                status="timed_out",
                verification_note=f"hit {per_run_timeout_s}s watchdog (possible converse deadlock)",
                latency_s=float(per_run_timeout_s),
            )
        except Exception as e:  # noqa: BLE001
            last_error = e
            print(f"  retry[{attempt}] {prompt_id}: run raised: {e}", flush=True)
            continue
        m = outcome.metrics
        if m.status == "completed" or attempt >= retries:
            return m
        print(f"  retry[{attempt}] {prompt_id}: status={m.status} -> re-run", flush=True)
    return RunMetrics(
        prompt_id=prompt_id,
        task_id=task.id,
        status="errored",
        verification_note=f"run_one raised: {last_error}",
        latency_s=0.0,
    )


def _metric_dict(m: RunMetrics) -> dict:
    return {k: v for k, v in m.__dict__.items() if k != "extra"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Communication comparison bed (real LLM)")
    parser.add_argument("--smoke", action="store_true",
                        help="quick sanity: 1 cell (off), interdependent task, 1 replicate")
    parser.add_argument("--cells", default=",".join(CELLS), help="comma-separated cell list")
    parser.add_argument("--tasks", default="independent,interdependent",
                        help="comma-separated task modes (independent, interdependent)")
    parser.add_argument("--replicates", type=int, default=1, help="replicates per cell")
    parser.add_argument("--retries", type=int, default=1,
                        help="re-attempts for runs that do not complete cleanly")
    parser.add_argument("--timeout-s", type=int, default=1200,
                        help="hard watchdog per run (cancels deadlocked/slow runs)")
    args = parser.parse_args()

    if args.smoke:
        args.cells = "off"
        args.tasks = "interdependent"
        args.replicates = 1

    config = load_harness_config()
    api_key = merge_api_key(config)
    if not api_key:
        print("Error: no API key found (OPENROUTER_API_KEY / OPENAI_API_KEY)", file=sys.stderr)
        sys.exit(1)

    task_modes = args.tasks.split(",")
    tasks = [t for t in COLLAB_TASKS if t.mode in task_modes]
    cells = tuple(args.cells.split(","))
    unknown = [c for c in cells if c not in CELLS]
    if unknown:
        print(f"Error: unknown cells {unknown} (use: {', '.join(CELLS)})", file=sys.stderr)
        sys.exit(1)

    llm = _make_llm(config, api_key)
    print(f"LLM: {config.llm.model} | cells: {', '.join(cells)} | tasks: {task_modes} | reps: {args.replicates}", flush=True)
    ws = _stage_workspace()
    print(f"workspace: {ws}", flush=True)

    collector = _make_collector(config)

    async def run_async():
        results: list[RunMetrics] = []
        for cell in cells:
            factory = runtime_factory_for(cell, llm=llm, trace_root=ws / "traces")
            for rep in range(args.replicates):
                for task in tasks:
                    prompt_id = f"{cell}#rep{rep}"
                    m = await _run_with_retry(
                        factory, task, prompt_id, ws, collector,
                        retries=args.retries, per_run_timeout_s=args.timeout_s,
                    )
                    results.append(m)
                    note = (m.verification_note or "").replace("\n", " ")[:50]
                    print(
                        f"  {cell:<16} {m.status:<9} correct={str(m.correct):<5} "
                        f"tokens={m.total_tokens} cost={m.cost_usd:.4f} "
                        f"turns={m.total_turns} agents={m.agent_count} "
                        f"latency={m.latency_s:.0f}s {note}",
                        flush=True,
                    )
        return results

    results = asyncio.run(run_async())

    summary = _summarize(results, cells)
    meta = {
        "when": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "model": config.llm.model,
        "base_url": config.llm.base_url,
        "task_ids": args.tasks,
        "replicates": args.replicates,
        "runs": len(results),
        "total_cost": round(sum(m.cost_usd for m in results), 4),
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "RESULTS.md").write_text(_render_markdown(meta, summary, results))
    (OUT_DIR / "metrics-cells.json").write_text(json.dumps([_metric_dict(m) for m in results], indent=2))

    print("\n=== PER-CELL SUMMARY ===")
    print(_render_markdown(meta, summary, results))
    print(f"\nReport: {OUT_DIR / 'RESULTS.md'}\nRaw: {OUT_DIR / 'metrics-cells.json'}")


def _make_collector(config):
    from .metrics import MetricsCollector
    return MetricsCollector(
        price_input_per_mtok=config.llm.price_input_per_mtok or 0.0,
        price_output_per_mtok=config.llm.price_output_per_mtok or 0.0,
    )


if __name__ == "__main__":
    main()