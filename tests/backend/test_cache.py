"""Tests that the conversation prefix the agent sends is actually cacheable.

Prompt caching (OpenAI / OpenRouter / DeepSeek) reuses a byte-identical *prefix*
across requests. Empirically (via scripts/cache_probe.py) a per-turn changing
observation message zeroes the provider cache entirely, while a strict
append-only conversation grows it. So the runtime must guarantee:

1. ``context.messages`` is strictly append-only — each new request is a *superset*
   of the previous one (system + user + committed turns only). No per-turn
   synthetic message.
2. Static steerage (environment / focus) is baked into a stable leading system
   message once at reset, so it stays cacheable.

A provider-aware fake LLM simulates the cache: it reports ``cached_tokens`` = the
token size of the longest prefix shared with the *entire* previous request
(which, under strict append-only, is the full previous request).
"""

from __future__ import annotations

import asyncio
import json

import pytest

from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import Task
from dynamic_harness.core.usage import UsageTracker
from dynamic_harness.llm.provider import LLMProvider, ToolCallData, ToolCallResponse


def msg_tokens(m: dict) -> int:
    """Token estimate mirroring AgentContext.estimate_prompt_tokens."""
    tail = 0
    for tc in m.get("tool_calls") or []:
        tail += len(json.dumps(tc.get("function", {}).get("arguments", "")))
    return max(1, (len(str(m.get("content"))) + tail) // 4)


def has_observation(payload: list[dict]) -> bool:
    return any(
        m.get("role") == "system" and "Context Observation" in str(m.get("content"))
        for m in payload
    )


class _CacheAwareProvider(LLMProvider):
    """Replays the provider's prefix-cache logic against the real payloads."""

    def __init__(self, tool_turns: int = 3) -> None:
        self.tool_turns = tool_turns
        self.payloads: list[list[dict]] = []
        self.usages: list[dict] = []
        self.session_ids: list[str] = []
        self._turns: dict[str, int] = {}

    def _simulate_cached(self, cur: list[dict], prev: list[dict] | None) -> int:
        if prev is None:
            return 0
        shared = 0
        for a, b in zip(cur, prev):
            if a != b:
                break
            shared += msg_tokens(a)
        return shared

    async def generate_with_tools(self, messages: list[dict], tools: list[dict], config=None):
        self.payloads.append([dict(m) for m in messages])
        sid = config.session_id if config else None
        self.session_ids.append(sid)
        self._turns[sid] = self._turns.get(sid, 0) + 1
        cached = self._simulate_cached(self.payloads[-1], self.payloads[-2] if len(self.payloads) > 1 else None)
        usage = {"prompt_tokens": 1000, "completion_tokens": 5, "cached_tokens": cached}
        self.usages.append(usage)
        if self._turns[sid] <= self.tool_turns:
            n = self._turns[sid]
            return ToolCallResponse(
                tool_calls=[ToolCallData(id=f"call_{n}", name="bash", arguments={"command": f"echo step {n}"})],
                model="m",
                usage=usage,
            )
        return ToolCallResponse(content="done", model="m", usage=usage)

    async def generate(self, system: str, user: str, config=None):
        return ToolCallResponse(content="ok", model="m", usage=None)  # type: ignore[return-value]

    async def generate_structured(self, system: str, user: str, response_model, config=None):
        return None


@pytest.mark.asyncio
async def test_payload_is_strict_append_only_and_cache_grows(runtime: Runtime) -> None:
    provider = _CacheAwareProvider(tool_turns=3)
    runtime.set_llm(provider)
    agent = runtime.delegate(Task(description="probe"))
    await agent.run()

    payloads = provider.payloads
    assert len(payloads) == 4  # 3 tool turns + final text reply

    # No per-turn observation anywhere — the stream is pure turns.
    for p in payloads:
        assert not has_observation(p)
    assert not has_observation(agent.context.messages)

    # Strict append-only: each request is a superset of the previous.
    for i in range(1, len(payloads)):
        assert payloads[i][: len(payloads[i - 1])] == payloads[i - 1]

    # cached_tokens = the FULL previous request (no trailing-message loss).
    for i in range(1, len(payloads)):
        assert provider.usages[i]["cached_tokens"] == sum(msg_tokens(m) for m in payloads[i - 1])

    # Growth: monotonic, and well past the [system, user] intro.
    cached_seq = [u["cached_tokens"] for u in provider.usages]
    intro_tokens = msg_tokens(payloads[0][0]) + msg_tokens(payloads[0][1])
    assert cached_seq[0] == 0
    assert cached_seq[1] == intro_tokens
    assert cached_seq == sorted(cached_seq)
    assert cached_seq[-1] > intro_tokens

    # Those per-request figures were recorded into the usage tracker.
    usage = runtime.get_usage(agent.id)
    assert usage["cached_tokens"] == sum(cached_seq)


@pytest.mark.asyncio
async def test_long_agent_cache_grows_past_intro(runtime: Runtime) -> None:
    """With 4+ LLM turns the cache must grow well beyond the static intro and
    re-cache the entire accumulated history each turn (no one-turn lag)."""
    provider = _CacheAwareProvider(tool_turns=5)
    runtime.set_llm(provider)
    agent = runtime.delegate(Task(description="probe"))
    await agent.run()

    payloads = provider.payloads
    assert len(payloads) == 6  # 5 tool turns + final text reply

    cached_seq = [u["cached_tokens"] for u in provider.usages]
    assert cached_seq[0] == 0
    intro_tokens = msg_tokens(payloads[0][0]) + msg_tokens(payloads[0][1])

    # Pure append-only -> each request fully subsumes the previous.
    for i in range(1, len(payloads)):
        assert payloads[i][: len(payloads[i - 1])] == payloads[i - 1]
        assert provider.usages[i]["cached_tokens"] == sum(msg_tokens(m) for m in payloads[i - 1])

    # Monotonic growth, and by request 3+ the cache has swallowed real history.
    assert cached_seq == sorted(cached_seq)
    assert len(set(cached_seq)) == len(cached_seq)  # strictly increasing
    assert cached_seq[1] == intro_tokens            # turn 1: only the intro is stable
    assert cached_seq[3] > intro_tokens             # turn 3: committed turns are cached
    assert cached_seq[-1] > cached_seq[len(payloads) // 2]

    # No per-turn observation lands in the persisted history.
    assert not has_observation(agent.context.messages)

    # Every request of the conversation carries the SAME per-agent session_id.
    assert len(set(provider.session_ids)) == 1
    assert provider.session_ids[0] == agent.session_id


@pytest.mark.asyncio
async def test_distinct_agents_get_distinct_session_ids(runtime: Runtime) -> None:
    """Each conversation (agent) must pin its own session so caches stay
    conversation-scoped, never cross-contaminating between parallel agents."""
    provider = _CacheAwareProvider(tool_turns=1)
    runtime.set_llm(provider)
    a = runtime.delegate(Task(description="A"))
    b = runtime.delegate(Task(description="B"))
    await asyncio.gather(a.run(), b.run())

    assert len(provider.session_ids) == 4  # 2 agents x 2 requests each
    seen = set(provider.session_ids)
    assert seen == {a.session_id, b.session_id}
    assert seen == {a.id, b.id}


@pytest.mark.asyncio
async def test_prune_busts_prefix_cache(runtime: Runtime) -> None:
    """``prune()`` replaces middle turns with PRUNED markers, so the next request
    is no longer a strict superset of the previous one. That divergence is a
    deliberate cache-buster: only the stable leading system+user intro survives.
    This pins the trade-off — strict append-only is what keeps the cache warm,
    and any in-place context mutation sacrifices it (the price of prune/compress)."""
    from dynamic_harness.core.context import AgentContext

    ctx = AgentContext()
    ctx.reset("system prompt", "user start")
    provider = _CacheAwareProvider(tool_turns=0)

    def tool_turn(pid: int) -> tuple[dict, list[dict]]:
        cid = f"c{pid}"
        assistant = {
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": cid, "type": "function",
                "function": {"name": "bash", "arguments": json.dumps({"command": f"echo {pid}"})},
            }],
        }
        return assistant, [{"role": "tool", "tool_call_id": cid, "content": str(pid)}]

    async def send() -> None:
        await provider.generate_with_tools([dict(m) for m in ctx.messages], tools=[])

    # Warm the cache across two append-only turns.
    for pid in (1, 2):
        assistant, results = tool_turn(pid)
        ctx.commit_turn(assistant, results)
        await send()

    warm = provider.usages[-1]["cached_tokens"]
    assert warm > 0

    # Prune the first turn: the middle is replaced by a PRUNED marker.
    ctx.prune(["t0"])
    post = [dict(m) for m in ctx.messages]
    await send()

    intro_tokens = sum(msg_tokens(m) for m in post[:2])  # system + user intro
    assert provider.usages[-1]["cached_tokens"] == intro_tokens
    assert provider.usages[-1]["cached_tokens"] < warm


@pytest.mark.asyncio
async def test_cached_tokens_record_and_accumulate() -> None:
    tracker = UsageTracker()
    await tracker.record_usage("a1", prompt_tokens=1000, completion_tokens=10, cached_tokens=3328)
    await tracker.record_usage("a1", prompt_tokens=2000, completion_tokens=10, cached_tokens=1500)
    assert tracker.get_usage("a1")["cached_tokens"] == 4828
    assert tracker.total_usage()["cached_tokens"] == 4828

    await tracker.record_usage("a2", prompt_tokens=500, completion_tokens=5, cached_tokens=100)
    assert tracker.total_usage()["cached_tokens"] == 4928
    assert tracker.get_usage("a2")["total_tokens"] == 505