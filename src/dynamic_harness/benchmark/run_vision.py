"""P4 — live vision probe: send a rendered image to a real LLM.

Usage (from the repo root):

  python -m dynamic_harness.benchmark.run_vision --smoke
  python -m dynamic_harness.benchmark.run_vision --replicates 3 --seed 7

The probe renders a fresh random 4-digit code into the staged workspace's
``resources/_vision/code.png`` (the code exists nowhere else — not in the
source tree, not in the prompt), runs one default-topology agent per
replicate with the real configured LLM, and verifies the produced
``code.txt`` against the PNG pixels mechanically. A correct answer is only
possible if the whole chain works end-to-end: the ``read`` tool attached the
image as a data URI, the provider forwarded the ``image_url`` content part,
and the model actually saw the pixels. Results are written as a markdown
report + raw metrics JSON under
``../../../docs/breakdown/06-evolution/investigations/vision-live/``.

The configured model must be vision-capable; a text-only model completes the
run but fails verification (``mismatch``/``nothing`` in the note), which is
itself the diagnostic signal.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

from ..config import load_harness_config
from ..llm.registry import ProviderRegistry
from .comms import runtime_factory_for
from .run_comms import (  # shared with the comms bed — one canonical implementation
    _make_collector,
    _metric_dict,
    _run_with_retry,
    _stage_workspace,
    REPO_ROOT,
)
from .tasks import VisionCodeTask
from .vision_asset import VISION_DIGITS, render_code_image

load_dotenv()

OUT_DIR = REPO_ROOT / "docs" / "breakdown" / "06-evolution" / "investigations" / "vision-live"


def _render_markdown(meta: dict, results: list) -> str:
    lines = [
        "# Live vision probe — image → real LLM",
        "",
        f"- When: `{meta['when']}`",
        f"- Model: `{meta['model']}`",
        f"- Base: `{meta['base_url']}`",
        f"- Replicates: {meta['replicates']} · Runs: {meta['runs']} · "
        f"Correct: {meta['correct']}/{meta['runs']}",
        f"- Total cost: ${meta['total_cost']:.4f}",
        "",
        "| rep | status | correct | tokens | cost $ | turns | agents | note |",
        "|----:|--------|---------|-------:|-------:|------:|-------:|------|",
    ]
    for m in results:
        note = (m.verification_note or "").replace("|", "/")[:60]
        lines.append(
            f"| {m.prompt_id.rsplit('rep', 1)[-1]} | {m.status} | {m.correct} | "
            f"{m.total_tokens} | {m.cost_usd:.4f} | {m.total_turns} | "
            f"{m.agent_count} | {note} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Live vision probe (real LLM)")
    parser.add_argument("--smoke", action="store_true",
                        help="quick sanity: 1 replicate, random code")
    parser.add_argument("--replicates", type=int, default=1, help="replicates")
    parser.add_argument("--retries", type=int, default=1,
                        help="re-attempts for runs that do not complete cleanly")
    parser.add_argument("--timeout-s", type=int, default=1200,
                        help="hard watchdog per run (cancels deadlocked/slow runs)")
    parser.add_argument("--seed", type=int, default=None,
                        help="seed for the code (default: random per run)")
    args = parser.parse_args()
    replicates = 1 if args.smoke else args.replicates

    config = load_harness_config()
    registry = ProviderRegistry.from_config(config)
    api_key = registry.api_key_for(registry.active_provider_id)
    if not api_key:
        print("Error: no API key found (OPENROUTER_API_KEY / OPENAI_API_KEY)", file=sys.stderr)
        sys.exit(1)

    llm = registry.select()
    ws = _stage_workspace()
    rng = random.Random(args.seed)  # seed=None → system entropy
    code = "".join(rng.choices("0123456789", k=VISION_DIGITS))
    png = ws / "resources" / "_vision" / "code.png"
    png.parent.mkdir(parents=True, exist_ok=True)
    render_code_image(png, code)
    print(f"LLM: {config.root_model} | code: {code} | replicates: {replicates}", flush=True)
    print(f"workspace: {ws}", flush=True)

    task = VisionCodeTask()
    factory = runtime_factory_for("off", llm=llm, trace_root=ws / "traces")
    collector = _make_collector(registry)

    async def run_async():
        results = []
        for rep in range(replicates):
            m = await _run_with_retry(
                factory, task, f"vision#rep{rep}", ws, collector,
                retries=args.retries, per_run_timeout_s=args.timeout_s,
            )
            results.append(m)
            note = (m.verification_note or "").replace("\n", " ")[:50]
            print(
                f"  rep{rep} {m.status:<9} correct={str(m.correct):<5} "
                f"tokens={m.total_tokens} cost={m.cost_usd:.4f} "
                f"turns={m.total_turns} latency={m.latency_s:.0f}s {note}",
                flush=True,
            )
        return results

    results = asyncio.run(run_async())

    meta = {
        "when": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "model": config.root_model,
        "base_url": config.providers[registry.active_provider_id].base_url,
        "replicates": replicates,
        "runs": len(results),
        "correct": sum(1 for m in results if m.correct),
        "total_cost": round(sum(m.cost_usd for m in results), 4),
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "RESULTS.md").write_text(_render_markdown(meta, results))
    (OUT_DIR / "metrics-vision.json").write_text(
        json.dumps([_metric_dict(m) for m in results], indent=2)
    )

    print("\n=== VISION PROBE SUMMARY ===")
    print(_render_markdown(meta, results))
    print(f"\nReport: {OUT_DIR / 'RESULTS.md'}\nRaw: {OUT_DIR / 'metrics-vision.json'}")


if __name__ == "__main__":
    main()
