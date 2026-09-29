"""Benchmark the ``codeact`` agent type (single ``invoke`` surface) against the
default 34-tool agent on the same ALL_TASKS suite — the code-as-action
investigation's decision gate (proposal §5).

Usage:
  python -m dynamic_harness.benchmark.run_codeact [--keep-workspace]

The gate: promote code-as-action to an IMP only if the measured delta is a
**token reduction at ≥ parity success**, or a **success gain at ≤ parity
cost**. This script prints the side-by-side and writes both metric JSONs under
``.optimize_benchmarks/codeact_{structured,codeact}.json`` plus a markdown
comparison, so the identity question (build-vs-extend) gets answered by
numbers, not narrative.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from ..config import load_harness_config, merge_api_key
from ..core.codeact import register_codeact
from ..core.runtime import Runtime
from ..llm.openai_provider import OpenAIProvider
from .metrics import MetricsCollector
from .runner import run_one, stage_workspace
from .tasks import ALL_TASKS

load_dotenv()

OUT_DIR = Path(".optimize_benchmarks")


def _make_runtime_factory(config, api_key: str, llm, codeact: bool):
    def factory() -> Runtime:
        rt = Runtime(
            artifact_root=Path(".dynamic-harness/artifacts"),
            repo_root=Path(".dynamic-harness/repo"),
            trace_root=Path(".dynamic-harness/traces"),
            config=config,
        )
        if codeact:
            register_codeact(rt)
        rt.set_llm(llm)
        return rt
    return factory


def _summary(runs: list) -> dict:
    n = len(runs)
    passed = sum(1 for r in runs if r.passed)
    return {
        "tasks": n,
        "passed": passed,
        "total_tokens": sum(r.total_tokens for r in runs),
        "total_turns": sum(r.total_turns for r in runs),
        "cost_usd": sum(r.cost_usd for r in runs),
        "latency_s": sum(r.latency_s for r in runs),
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="codeact vs structured-tool benchmark")
    parser.add_argument("--keep-workspace", action="store_true",
                        help="retain the staged snapshot workspace on disk")
    args = parser.parse_args()

    config = load_harness_config()
    api_key = merge_api_key()
    if not api_key:
        print("Error: no API key found", file=sys.stderr)
        sys.exit(1)

    llm = OpenAIProvider(
        model=config.llm.model,
        base_url=config.llm.base_url,
        api_key=api_key,
        verify_ssl=config.llm.verify_ssl,
        provider_ignore=config.llm.provider_ignore or None,
        provider_allow_fallbacks=config.llm.provider_allow_fallbacks,
        provider_force=config.llm.provider_force,
        timeout=config.llm.call_timeout_seconds,
    )

    collector = MetricsCollector(
        price_input_per_mtok=config.llm.price_input_per_mtok or 0.0,
        price_output_per_mtok=config.llm.price_output_per_mtok or 0.0,
    )
    f_structured = _make_runtime_factory(config, api_key, llm, codeact=False)
    f_codeact = _make_runtime_factory(config, api_key, llm, codeact=True)

    ws = stage_workspace(Path.cwd())
    print(f"LLM: {config.llm.model} | tasks: {len(ALL_TASKS)} | workspace: {ws}")

    try:
        runs_structured: list = []
        runs_codeact: list = []
        for task in ALL_TASKS:
            for label, factory, agent_type, sink, other in (
                ("structured", f_structured, None, runs_structured, runs_codeact),
                ("codeact", f_codeact, "codeact", runs_codeact, runs_structured),
            ):
                outcome = await run_one(
                    runtime_factory=factory,
                    task=task,
                    prompt_id=label,
                    collector=collector,
                    workspace=ws,
                    agent_type=agent_type,
                )
                sink.append(outcome.metrics)
                m = outcome.metrics
                verdict = "PASS" if outcome.passed else "FAIL"
                print(
                    f"  [{label}] {task.id} {verdict} tokens={m.total_tokens} "
                    f"turns={m.total_turns} cost={m.cost_usd:.4f} lat={m.latency_s:.1f}s"
                )

        s, c = _summary(runs_structured), _summary(runs_codeact)
        print("\n=== SUMMARY ===")
        print(f"structured: {s}")
        print(f"codeact:    {c}")

        delta_tokens = (c["total_tokens"] - s["total_tokens"]) / max(1, s["total_tokens"])
        delta_success = c["passed"] - s["passed"]
        delta_cost = c["cost_usd"] - s["cost_usd"]
        print("\n=== GATE (proposal §5) ===")
        print(f"token delta : {delta_tokens:+.1%}  (reduction at ≥ parity success would promote)")
        print(f"success     : {delta_success:+d}/{s['tasks']} tasks (gain at ≤ parity cost would promote)")
        print(f"cost delta  : ${delta_cost:+.4f}")

        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / "codeact_structured.json").write_text(
            json.dumps([asdict_run(r) for r in runs_structured], indent=2)
        )
        (OUT_DIR / "codeact_codeact.json").write_text(
            json.dumps([asdict_run(r) for r in runs_codeact], indent=2)
        )
        _write_comparison(ws, runs_structured, runs_codeact, s, c)
    finally:
        import shutil
        if not args.keep_workspace:
            shutil.rmtree(ws, ignore_errors=True)


def asdict_run(metrics) -> dict:
    from dataclasses import asdict
    return asdict(metrics)


def _write_comparison(ws: Path, structured: list, codeact: list, s: dict, c: dict) -> None:
    """Per-task side-by-side markdown under .optimize_benchmarks/codeact.md."""
    lines = [
        "# codeact vs structured — per-task comparison",
        "",
        f"LLM: {ws} (staged workspace)",
        "",
        "| task | structured | codeact | Δtokens | Δturns |",
        "|---|---|---|---|---|",
    ]
    for a, b in zip(structured, codeact):
        dt = b.total_tokens - a.total_tokens
        dn = b.total_turns - a.total_turns
        lines.append(
            f"| {a.task_id} | {'PASS' if a.passed else 'FAIL'} "
            f"({a.total_tokens}t/{a.total_turns}n) | "
            f"{'PASS' if b.passed else 'FAIL'} ({b.total_tokens}t/{b.total_turns}n) | "
            f"{dt:+d} | {dn:+d} |"
        )
    lines += [
        "",
        "## Totals",
        "",
        f"- structured: {s}",
        f"- codeact:    {c}",
        "",
        f"Gate: token delta {(c['total_tokens'] - s['total_tokens']) / max(1, s['total_tokens']):+.1%}, "
        f"success delta {c['passed'] - s['passed']:+d} tasks, "
        f"cost delta ${c['cost_usd'] - s['cost_usd']:+.4f}.",
    ]
    (OUT_DIR / "codeact.md").write_text("\n".join(lines))


if __name__ == "__main__":
    asyncio.run(main())