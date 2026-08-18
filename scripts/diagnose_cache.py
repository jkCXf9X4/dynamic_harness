#!/usr/bin/env python3
"""Diagnose prompt-cache behavior from a real run's JSONL trace.

For each agent, pairs every recorded ``llm_request`` with its ``llm_response``
and prints:

* the **reported** ``cached_tokens`` from the provider (``usage.cached_tokens``)
* the **wire** shared prefix with the previous request (what a byte-for-byte
  prefix cache *should* be able to reuse)

If the wire prefix grows (long agents) but the provider's number stays pinned at
the intro, the problem is provider-side. If the wire prefix is flat too, the
requests themselves are diverging — and we can inspect the payloads to find why.

Usage:
    python scripts/diagnose_cache.py --trace <trace_root> [--agent <id>] [--json]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_entries(trace_root: Path) -> dict[str, list[dict]]:
    agents: dict[str, list[dict]] = {}
    for d in trace_root.iterdir():
        if not d.is_dir():
            continue
        fp = d / "trace.jsonl"
        if not fp.exists():
            continue
        agents[d.name] = [json.loads(line) for line in fp.read_text().splitlines() if line.strip()]
    return agents


def _is_placeholder(text: str) -> bool:
    return text.startswith("<same as trace-entry #1")


def _pair_requests(entries: list[dict]) -> list[tuple[dict, dict | None]]:
    """Return (request_entry, following_response_entry) in order."""
    pairs: list[tuple[dict, dict | None]] = []
    last_req: dict | None = None
    for e in entries:
        if e["type"] == "llm_request":
            last_req = e
        elif e["type"] == "llm_response" and last_req is not None:
            pairs.append((last_req, e))
            last_req = None
    if last_req is not None:
        pairs.append((last_req, None))
    return pairs


def _shared_prefix_bytes(a: list[dict], b: list[dict]) -> int:
    """Longest common byte prefix of the serialized message lists."""
    sa = json.dumps(a, default=str)
    sb = json.dumps(b, default=str)
    k = 0
    while k < min(len(sa), len(sb)) and sa[k] == sb[k]:
        k += 1
    return k


def _normalize(entries: list[dict]) -> list[dict]:
    """Replace trace prefix-hash placeholders with the real first-entry texts."""
    first_req = next((e for e in entries if e["type"] == "llm_request"), None)
    if first_req is None:
        return entries
    real = first_req["messages"][:2]
    out = []
    for e in entries:
        if e["type"] != "llm_request":
            out.append(e)
            continue
        msgs = []
        for i, m in enumerate(e["messages"]):
            if i < 2 and isinstance(m.get("content"), str) and _is_placeholder(m["content"]):
                msgs.append(real[i])
            else:
                msgs.append(m)
        e = dict(e)
        e["messages"] = msgs
        out.append(e)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", required=True, type=Path, help="trace root dir")
    ap.add_argument("--agent", default=None, help="only this agent id")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    agents = _load_entries(args.trace)
    if args.agent:
        agents = {args.agent: agents[args.agent]} if args.agent in agents else {}

    for agent_id, entries in sorted(agents.items()):
        entries = _normalize(entries)
        pairs = _pair_requests(entries)
        if len(pairs) < 2:
            continue

        print(f"\n=== agent {agent_id} ({len(pairs)} requests) ===")
        print(f"{'req':<4}{'msgs':<6}{'wire_share_chars':<18}{'reported_cached':<16}{'share_est_tok':<14}msgs_len")
        prev_messages: list[dict] | None = None
        for i, (req, resp) in enumerate(pairs, 1):
            msgs = req["messages"]
            share = _shared_prefix_bytes(msgs, prev_messages) if prev_messages is not None else 0
            cached = None
            if resp and resp.get("usage"):
                cached = resp["usage"].get("cached_tokens")
            est = share // 4
            print(f"{i:<4}{len(msgs):<6}{share:<18}{str(cached):<16}{est:<14}{len(json.dumps(msgs, default=str))}")
            prev_messages = msgs

        if args.json:
            print(json.dumps({agent_id: len(pairs)}))


if __name__ == "__main__":
    main()
