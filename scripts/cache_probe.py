#!/usr/bin/env python3
"""Isolate why prompt caching plateaus.

Hits a real OpenAI-compatible provider with a multi-turn text-only conversation
in several request shapes and prints ``prompt_tokens_details.cached_tokens`` per
turn, so we can see which structure actually grows the cache.

Modes
-----
opencode         append-only messages, no synthetic trailing message (opencode-like)
harness          append-only messages + a changing per-turn trailing observation
harness-no-obs   append-only messages, no observation (isolates the observation)

Optional flags
--------------
--session <id>   send a stable OpenRouter ``session_id`` (session pinning)
--user-agent <s> override the User-Agent header (e.g. "opencode") to test whether
                 the provider treats identities differently

Usage
-----
OPENROUTER_API_KEY=... python scripts/cache_probe.py \
    --base-url https://openrouter.ai/api/v1 \
    --model deepseek/deepseek-v4-flash-0731 \
    --turns 6 --mode all
"""

from __future__ import annotations

import argparse
import asyncio
import os

import httpx
from openai import AsyncOpenAI

PROMPT = (
    "You are a caching probe. Respond to every message with exactly \"PONG\". "
    "Never vary your answer."
)


def _observation(turn: int) -> dict:
    # Mimics AgentContext.build_observation: a system message that changes each turn.
    return {
        "role": "system",
        "content": (
            f"[Context Observation]\nTurn: {turn}\nMessages in context: {turn + 3}\n"
            f"Estimated tokens: ~{1000 + turn * 250}\nYour next turn id: t{turn + 1}\n"
            f"Prune stale turns; there are {turn} committed."
        ),
    }


def _starts():
    return [
        {"role": "system", "content": PROMPT},
        {"role": "user", "content": "start now"},
    ]


async def _run_mode(client, model, mode: str, turns: int, session: str | None) -> list[int | None]:
    history = _starts()
    cached: list[int | None] = []
    for t in range(turns):
        if mode == "opencode":
            sent = list(history)
        elif mode == "harness":
            sent = list(history) + [_observation(t + 1)]
        else:  # harness-no-obs
            sent = list(history)

        kwargs = dict(model=model, messages=sent, temperature=0.0)
        if session:
            kwargs["extra_body"] = {"session_id": session}
        resp = await client.chat.completions.create(**kwargs)

        details = getattr(resp.usage, "prompt_tokens_details", None) if resp.usage else None
        c = getattr(details, "cached_tokens", None) if details else None
        cached.append(c)

        reply = resp.choices[0].message.content or "PONG"
        history.append({"role": "assistant", "content": reply})
        history.append({"role": "user", "content": f"continue {t + 1}"})
    return cached


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--api-key", default=None, help="defaults to OPENROUTER_API_KEY")
    ap.add_argument("--turns", type=int, default=6)
    ap.add_argument("--mode", default="all",
                    choices=["all", "opencode", "harness", "harness-no-obs"])
    ap.add_argument("--session", default=None)
    ap.add_argument("--user-agent", default=None)
    ap.add_argument("--no-verify-ssl", action="store_true",
                    help="disable TLS verification (self-signed corporate proxy)")
    args = ap.parse_args()

    key = args.api_key or os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("no API key (set --api-key or OPENROUTER_API_KEY)")

    headers = {"Authorization": f"Bearer {key}"}
    if args.user_agent:
        headers["User-Agent"] = args.user_agent
    client = AsyncOpenAI(
        base_url=args.base_url,
        api_key=key,
        default_headers=headers,
        http_client=httpx.AsyncClient(verify=not args.no_verify_ssl),
    )

    modes = ["opencode", "harness", "harness-no-obs"] if args.mode == "all" else [args.mode]
    print(f"model={args.model}  turns={args.turns}  session={'stable' if args.session else 'none'}  UA={args.user_agent or 'default'}")
    print(f"{'mode':<15}" + "".join(f"t{t + 1:<6}" for t in range(args.turns)) + "growth")

    for mode in modes:
        got = await _run_mode(client, args.model, mode, args.turns, args.session)
        growth = "+" if got and got[-1] and got[0] is not None and got[-1] > (got[0] or 0) else "flat"
        print(f"{mode:<15}" + "".join(f"{('-' if c is None else str(c)):<7}" for c in got) + growth)

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
