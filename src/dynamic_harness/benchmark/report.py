"""Write benchmark results to disk (JSON + Markdown) for transparency/traceability."""

from __future__ import annotations

import json
from pathlib import Path

from .metrics import RunMetrics
from .scoring import PromptResult


def _metrics_to_dict(m: RunMetrics) -> dict:
    return {
        "prompt_id": m.prompt_id,
        "task_id": m.task_id,
        "status": m.status,
        "correct": m.correct,
        "verification_note": m.verification_note,
        "total_tokens": m.total_tokens,
        "prompt_tokens": m.prompt_tokens,
        "completion_tokens": m.completion_tokens,
        "cost_usd": round(m.cost_usd, 6),
        "agent_count": m.agent_count,
        "max_depth": m.max_depth,
        "delegations": m.delegations,
        "message_count": m.message_count,
        "total_turns": m.total_turns,
        "llm_retries": m.llm_retries,
        "failures": m.failures,
        "escalations": m.escalations,
        "latency_s": round(m.latency_s, 2),
    }


def write_metrics_json(runs: list[RunMetrics], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([_metrics_to_dict(r) for r in runs], indent=2))


def _row(m: RunMetrics) -> str:
    mark = {
        True: "PASS",
        False: "FAIL",
        None: "n.a.",
    }.get(m.correct, "?")
    return (
        f"| {m.prompt_id:<8} | {m.task_id:<10} | {mark:<5} | {m.total_tokens:>9} | "
        f"{m.cost_usd:>8.4f} | {m.total_turns:>6} | {m.max_depth:>5} | "
        f"{m.agent_count:>6} | {m.delegations:>7} | {m.latency_s:>6.1f} |"
    )


def write_markdown(runs: list[RunMetrics], ranked: list[PromptResult], path: Path) -> None:
    lines: list[str] = [
        "# Benchmark Metrics Report",
        "",
        "Per (prompt, task) run — objective, comparable.",
        "",
        "| Prompt | Task | Verdict | Tokens | Cost($) | Turns | Depth | Agents | Deleg | Lat(s) |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for m in runs:
        lines.append(_row(m))

    lines += ["", "## Ranked Prompts (higher score = better)", ""]
    lines += ["| Rank | Prompt | Pass | Tokens | Cost($) | Turns | Depth | Eff | Score |", "|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(ranked, 1):
        lines.append(
            f"| {i} | {r.prompt_id:<8} | {r.tasks_passed}/{r.tasks_total} | "
            f"{r.total_tokens:>9} | {r.total_cost:>7.4f} | {r.total_turns:>6} | "
            f"{r.max_depth:>5} | {r.efficiency_score:>5.2f} | {r.final_score:>5.3f} |"
        )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))
