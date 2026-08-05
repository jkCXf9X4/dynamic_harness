"""Optimize the agent system prompt using the programmatic benchmark harness.

Flow (2 rounds):
  Round 1: an LLM *generation agent* writes 5 seed-based variants to disk.
           The benchmark harness then objectively measures SEED + 5 variants
           against every benchmark task (fresh Runtime per run, failable
           ground-truth verifiers) and ranks them on data.
  Round 2: the top-3 from round 1 are handed to an LLM *refinement agent*,
           which writes 3 combined variants. The harness measures top-3 + 3
           new variants and ranks again.

The LLM only does creative generation; all measurement/ranking is deterministic
and in-process (see dynamic_harness.benchmark).
"""
import asyncio
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from dynamic_harness.benchmark import Benchmark
from dynamic_harness.benchmark.scoring import format_scores
from dynamic_harness.config import load_harness_config, merge_api_key
from dynamic_harness.core.agent import AGENT_SYSTEM_PROMPT
from dynamic_harness.core.runner import AgentRunner
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import ActivityEvent, ActivityEventType
from dynamic_harness.llm.openai_provider import OpenAIProvider

load_dotenv()

OUT_DIR = Path(".optimize_benchmarks")
ROUND1_VARIANTS = OUT_DIR / "variants.json"
ROUND2_VARIANTS = OUT_DIR / "variants_round2.json"
TOP_N = 3


def on_activity(event: ActivityEvent) -> None:
    et = event.event_type
    d = event.data
    aid = event.agent_id[:8]
    if et == ActivityEventType.DELEGATION_START:
        print(f"  [{aid}] → delegate: {d.get('description', '')[:80]}", flush=True)
    elif et == ActivityEventType.ITERATION:
        print(f"  [{aid}] turn {d.get('turn', '?')}, msgs {d.get('messages', '?')}", flush=True)
    elif et == ActivityEventType.TOOL_CALL_START:
        name = d.get("tool_name", "?")
        if name in ("read", "write", "bash"):
            print(f"  [{aid}] {name}({(d.get('arguments', {}) or {}).get('path', d.get('arguments', {}).get('command', ''))})", flush=True)


def _make_llm(config, api_key: str) -> OpenAIProvider:
    return OpenAIProvider(
        model=config.llm.model,
        base_url=config.llm.base_url,
        api_key=api_key,
        verify_ssl=False,
        provider_ignore=config.llm.provider_ignore or None,
        provider_allow_fallbacks=config.llm.provider_allow_fallbacks,
    )


def _runtime(config) -> Runtime:
    rt = Runtime(
        artifact_root=Path(".dynamic-harness/artifacts"),
        repo_root=Path(".dynamic-harness/repo"),
        trace_root=Path(".dynamic-harness/traces"),
        config=config,
    )
    return rt


async def _run_generation(config, llm, prompt_path: Path) -> None:
    """Run a generation agent that writes variant JSON to disk."""
    rt = _runtime(config)
    rt.set_llm(llm)
    rt.on_activity(on_activity)
    runner = AgentRunner(rt)
    prompt = prompt_path.read_text()
    await runner.run(prompt)
    if rt.trace_store:
        rt.trace_store.clear()


def _load_variants(path: Path, prefix: str) -> dict[str, str | None]:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a JSON object of id -> prompt text")
    prompts: dict[str, str | None] = {}
    for i, (k, v) in enumerate(data.items(), 1):
        if not isinstance(v, str):
            raise ValueError(f"{path}: value for '{k}' is not a string")
        prompts[f"{prefix}{i}"] = v
    return prompts


def _progress(line: str) -> None:
    print(line, flush=True)


async def main() -> None:
    config = load_harness_config()
    api_key = merge_api_key()
    if not api_key:
        print("Error: no API key found. Set OPENROUTER_API_KEY in ~/.bashrc")
        sys.exit(1)

    llm = _make_llm(config, api_key)
    print(f"LLM: {config.llm.model}", flush=True)
    print(f"Base: {config.llm.base_url}", flush=True)

    def runtime_factory() -> Runtime:
        rt = _runtime(config)
        rt.set_llm(llm)
        return rt

    benchmark = Benchmark(
        runtime_factory=runtime_factory,
        output_dir=OUT_DIR,
        price_input_per_mtok=config.llm.price_input_per_mtok or 0.0,
        price_output_per_mtok=config.llm.price_output_per_mtok or 0.0,
    )

    # ── Round 1: generate 5 variants ─────────────────────────────────────
    print("\n=== ROUND 1: generate 5 variants ===", flush=True)
    ROUND1_VARIANTS.unlink(missing_ok=True)
    t0 = time.monotonic()
    await _run_generation(config, llm, Path("prompts/generate_variants.prompt"))
    variants1 = _load_variants(ROUND1_VARIANTS, "v")
    print(f"Round 1 generation done in {time.monotonic()-t0:.0f}s: {list(variants1)}", flush=True)

    prompts1: dict[str, str | None] = {"seed": None}
    prompts1.update(variants1)

    print("\n=== ROUND 1: benchmark SEED + variants ===", flush=True)
    ranked1 = await benchmark.evaluate(prompts1, progress=_progress, report_stem="round1")

    ranks1 = ranked1[:TOP_N]
    winners = [r.prompt_id for r in ranks1]
    print("\n--- ROUND 1 RANKING ---", flush=True)
    print(format_scores(ranked1), flush=True)

    # ── Round 2: refine top 3 ────────────────────────────────────────────
    print("\n=== ROUND 2: refine top 3 ===", flush=True)
    refining = [prompts1[w] or AGENT_SYSTEM_PROMPT for w in winners]
    refine_prompt = (Path("prompts/refine_variants.prompt").read_text()
                     .replace("[INSERT WINNING PROMPT TEXTS HERE]",
                              "\n\n---\n\n".join(f"WINNING PROMPT {i+1}:\n{t}" for i, t in enumerate(refining))))

    ROUND2_VARIANTS.unlink(missing_ok=True)
    tmp_prompt_file = OUT_DIR / "_refine.prompt"
    tmp_prompt_file.write_text(refine_prompt)
    t0 = time.monotonic()
    await _run_generation(config, llm, tmp_prompt_file)
    tmp_prompt_file.unlink(missing_ok=True)
    variants2 = _load_variants(ROUND2_VARIANTS, "n")
    print(f"Round 2 refinement done in {time.monotonic()-t0:.0f}s: {list(variants2)}", flush=True)

    prompts2: dict[str, str | None] = {w: prompts1[w] for w in winners}
    prompts2.update(variants2)

    print("\n=== ROUND 2: benchmark top-3 + new variants ===", flush=True)
    ranked2 = await benchmark.evaluate(prompts2, progress=_progress, report_stem="round2")
    print("\n--- ROUND 2 RANKING ---", flush=True)
    print(format_scores(ranked2), flush=True)

    # ── Final: select best ───────────────────────────────────────────────
    best = ranked2[0]
    best_text = prompts2[best.prompt_id] or AGENT_SYSTEM_PROMPT
    best_path = OUT_DIR / "best_prompt.txt"
    best_path.write_text(best_text.strip() + "\n")

    print(f"\n=== RESULTS ===", flush=True)
    print(f"Best prompt: {best.prompt_id} (score {best.final_score:.3f}, "
          f"pass {best.tasks_passed}/{best.tasks_total})", flush=True)
    print(f"Wrote: {best_path}", flush=True)
    print(f"Reports: {OUT_DIR/'round1.md'}, {OUT_DIR/'round2.md'}, "
          f"{OUT_DIR/'round1.json'}, {OUT_DIR/'round2.json'}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
