"""Run the metric-driven prompt benchmark.

Usage:
  python -m dynamic_harness.benchmark.run        # compare SEED + variants
  python -m dynamic_harness.benchmark.run --seed-only
  python -m dynamic_harness.benchmark.run --report profile

Variants are read from a JSON file mapping prompt_id -> system_prompt text or
null (for the seed). By default every prompt is benchmarked against all tasks,
metrics are written to .optimize_benchmarks/metrics.json/.md, and prompts are
ranked by the weighted rubric.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from ..config import load_harness_config, merge_api_key
from ..core.runtime import Runtime
from ..llm.openai_provider import OpenAIProvider
from . import Benchmark
from .scoring import format_scores

load_dotenv()


def _make_runtime_factory(config, api_key: str, llm):
    def factory() -> Runtime:
        rt = Runtime(
            artifact_root=Path(".dynamic-harness/artifacts"),
            repo_root=Path(".dynamic-harness/repo"),
            trace_root=Path(".dynamic-harness/traces"),
            config=config,
        )
        rt.set_llm(llm)
        return rt
    return factory


def _load_prompts(path: Path, seed_only: bool) -> dict[str, str | None]:
    if seed_only:
        return {"seed": None}
    if path.exists():
        data = json.loads(path.read_text())
        if isinstance(data, dict):
            return {k: (v if v is not None else None) for k, v in data.items()}
    return {"seed": None}


def main() -> None:
    parser = argparse.ArgumentParser(description="Metric-driven prompt benchmark")
    parser.add_argument("--report", default="metrics", help="report stem (metrics|profile)")
    parser.add_argument("--seed-only", action="store_true", help="benchmark only the default prompt")
    parser.add_argument("--prompts", default=".optimize_benchmarks/benchmark_prompts.json",
                        help="path to prompts JSON (id -> system_prompt|null)")
    parser.add_argument("--keep-workspace", action="store_true",
                        help="retain the staged snapshot workspace on disk")
    args = parser.parse_args()

    config = load_harness_config()
    api_key = merge_api_key()
    if not api_key:
        print("Error: no API key found", file=sys.stderr)
        sys.exit(1)

    prompts = _load_prompts(Path(args.prompts), args.seed_only)
    print(f"LLM: {config.llm.model} | prompts: {list(prompts)}")

    llm = OpenAIProvider(
        model=config.llm.model,
        base_url=config.llm.base_url,
        api_key=api_key,
        verify_ssl=False,
        provider_ignore=config.llm.provider_ignore or None,
        provider_allow_fallbacks=config.llm.provider_allow_fallbacks,
    )

    benchmark = Benchmark(
        runtime_factory=_make_runtime_factory(config, api_key, llm),
        output_dir=Path(".optimize_benchmarks"),
        price_input_per_mtok=config.llm.price_input_per_mtok or 0.0,
        price_output_per_mtok=config.llm.price_output_per_mtok or 0.0,
    )

    def progress(line: str) -> None:
        print(line, flush=True)

    ranked = asyncio.run(benchmark.evaluate(
        prompts, progress=progress, report_stem=args.report,
        keep_workspace=args.keep_workspace,
    ))

    print("\n=== RANKED ===")
    print(format_scores(ranked))
    if ranked:
        print(f"\nBest: {ranked[0].prompt_id} (score {ranked[0].final_score:.3f})")
        print(f"Report: {Path('.optimize_benchmarks') / (args.report + '.md')}")


if __name__ == "__main__":
    main()
