"""A/B test: does the prune/restore toolset improve agent effectiveness?

Runs the objective Benchmark harness twice, both with the DEFAULT system prompt
(seed) and the same 4 benchmark tasks (incl. ``manyfiles``, a long-context probe
that accumulates many stale tool results):

  * ON  — the prune/restore tools are registered (default Runtime).
  * OFF — prune and restore are unregistered, so the agent cannot drop turns.

Metrics (ground-truth pass, prompt/completion tokens, cost, turns, and counts of
prune/restore/compress calls) are captured per run and compared. The only
difference between the two conditions is the availability of prune/restore.

Usage:
  source venv/bin/activate
  python scripts/run_prune_ab.py
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

from dotenv import load_dotenv

from dynamic_harness.benchmark import Benchmark
from dynamic_harness.benchmark.metrics import MetricsCollector
from dynamic_harness.benchmark.scoring import format_scores
from dynamic_harness.config import load_harness_config, merge_api_key
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.llm.openai_provider import OpenAIProvider

load_dotenv()

OUT = Path(".optimize_ab")
PROMPTS = {"seed": None}  # None => default agent system prompt


class AbCollector(MetricsCollector):
    """Add prune/restore/compress call counts and aggregate tool stats."""

    def _count_tool_calls(self, runtime) -> dict[str, int]:
        counts = {"prune": 0, "restore": 0, "compress": 0, "read": 0, "bash": 0}
        for _aid, agent in runtime.all_agents().items():
            seen: set[int] = set()
            msgs = list(agent.context.messages)
            for turn in agent.context.turns.values():
                for m in turn:
                    if id(m) not in seen:
                        seen.add(id(m))
                        msgs.append(m)
            for m in msgs:
                for tc in m.get("tool_calls") or []:
                    name = tc.get("function", {}).get("name")
                    if name in counts:
                        counts[name] += 1
        return counts

    def collect(self, runtime, **kw):
        m = super().collect(runtime, **kw)
        m.extra["tool_calls"] = self._count_tool_calls(runtime)
        return m


def _make_runtime_factory(config, llm, enable_prune: bool):
    def factory() -> Runtime:
        rt = Runtime(
            artifact_root=Path(".dynamic-harness/artifacts"),
            repo_root=Path(".dynamic-harness/repo"),
            trace_root=Path(".dynamic-harness/traces"),
            config=config,
        )
        rt.set_llm(llm)
        if not enable_prune:
            rt.tool_registry.unregister("prune")
            rt.tool_registry.unregister("restore")
        return rt
    return factory


def _fmt(metrics) -> str:
    tc = metrics.extra.get("tool_calls", {})
    return (
        f"task={metrics.task_id:<10} status={metrics.status:<9} "
        f"pass={metrics.passed!s:<5} tokens={metrics.total_tokens:<6} "
        f"prompt={metrics.prompt_tokens:<6} cost={metrics.cost_usd:.4f} "
        f"turns={metrics.total_turns:<5} latency={metrics.latency_s:.1f}s "
        f"prune={tc.get('prune',0)} restore={tc.get('restore',0)} "
        f"compress={tc.get('compress',0)}"
    )


async def _run(enabled: bool, config, llm) -> list:
    label = "ON" if enabled else "OFF"
    bench = Benchmark(
        runtime_factory=_make_runtime_factory(config, llm, enabled),
        output_dir=OUT / label.lower(),
        price_input_per_mtok=config.llm.price_input_per_mtok or 0.0,
        price_output_per_mtok=config.llm.price_output_per_mtok or 0.0,
        collector=AbCollector(),
    )

    def progress(line: str) -> None:
        print(f"  [{label}] {line}", flush=True)

    print(f"\n=== prune/restore {label} ===", flush=True)
    ranked = await bench.evaluate(PROMPTS, progress=progress, report_stem="bench")
    runs = ranked[0].per_task if ranked else []
    print(f"--- {label} per-run ---", flush=True)
    for r in sorted(runs, key=lambda x: x.task_id):
        print(f"  {_fmt(r)}", flush=True)
    print(f"--- {label} aggregate ---", flush=True)
    print(format_scores(ranked), flush=True)
    return runs


async def main() -> None:
    config = load_harness_config()
    api_key = merge_api_key()
    if not api_key:
        raise SystemExit("Error: no API key found. Set OPENROUTER_API_KEY.")

    llm = OpenAIProvider(
        model=config.llm.model,
        base_url=config.llm.base_url,
        api_key=api_key,
        verify_ssl=False,
        provider_ignore=config.llm.provider_ignore or None,
        provider_allow_fallbacks=config.llm.provider_allow_fallbacks,
        provider_force=config.llm.provider_force,
    )
    print(f"LLM: {config.llm.model} | base: {config.llm.base_url}", flush=True)

    t0 = time.monotonic()
    on_runs = await _run(True, config, llm)
    off_runs = await _run(False, config, llm)
    elapsed = time.monotonic() - t0

    print("\n=== COMPARISON (ON = with prune/restore, OFF = without) ===")
    by_task = {r.task_id: r for r in on_runs}
    header = (f"{'task':<10}{'cond':<5}{'pass':<6}{'tokens':>8}{'prompt':>8}"
              f"{'cost$':>9}{'turns':>7}{'prune':>6}{'restore':>8}")
    print(header)
    for r in sorted(off_runs, key=lambda x: x.task_id):
        o = by_task.get(r.task_id)
        for lr, lab in ((o, "ON"), (r, "OFF")):
            if lr is None:
                continue
            tc = lr.extra.get("tool_calls", {})
            print(
                f"{lr.task_id:<10}{lab:<5}{str(lr.passed):<6}"
                f"{lr.total_tokens:>8}{lr.prompt_tokens:>8}{lr.cost_usd:>9.4f}"
                f"{lr.total_turns:>7}{tc.get('prune',0):>6}{tc.get('restore',0):>8}"
            )

    def agg(runs):
        return {
            "passed": sum(1 for r in runs if r.passed),
            "total": len(runs),
            "tokens": sum(r.total_tokens for r in runs),
            "prompt": sum(r.prompt_tokens for r in runs),
            "cost": sum(r.cost_usd for r in runs),
            "turns": sum(r.total_turns for r in runs),
        }

    A, B = agg(on_runs), agg(off_runs)
    print("\nTotals")
    print(f"  ON : pass {A['passed']}/{A['total']}  tokens {A['tokens']}  "
          f"prompt {A['prompt']}  cost ${A['cost']:.4f}  turns {A['turns']}")
    print(f"  OFF: pass {B['passed']}/{B['total']}  tokens {B['tokens']}  "
          f"prompt {B['prompt']}  cost ${B['cost']:.4f}  turns {B['turns']}")
    delta_tokens = A["tokens"] - B["tokens"]
    print(f"  delta tokens: {delta_tokens:+d} "
          f"({(delta_tokens / max(1, B['tokens']) * 100):+.1f}% vs OFF)")
    print(f"\nTotal wall time: {elapsed:.0f}s. Reports under {OUT}/")


if __name__ == "__main__":
    asyncio.run(main())
