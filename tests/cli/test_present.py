from __future__ import annotations

import asyncio
import inspect

import pytest

from dynamic_harness.cli import present
from dynamic_harness.cli.present import (
    AgentNode,
    build_agent_tree,
    build_stats,
    cache_hit_rate,
)
from dynamic_harness.core.task import Task, TaskStatus


def _seed(runtime, *, n: int = 1) -> list[str]:
    ids = []
    for i in range(n):
        agent = runtime.delegate(Task(description=f"task-{i}"))
        ids.append(agent.id)
    return ids


class TestAgentNode:
    def test_short_id_clips_to_8(self) -> None:
        node = AgentNode(agent_id="a" * 12, description="d", status="running")
        assert node.short_id == "a" * 8

    def test_short_description_clips_to_40(self) -> None:
        node = AgentNode(agent_id="id", description="x" * 100, status="running")
        assert len(node.short_description) == 40

    def test_usage_empty_when_no_counts(self) -> None:
        node = AgentNode(agent_id="id", description="d", status="running")
        assert node.usage == ""

    def test_usage_shows_tokens_and_messages(self) -> None:
        node = AgentNode(agent_id="id", description="d", status="running", tokens=100, messages=3)
        assert node.usage == " (100t, 3msgs)"

    def test_usage_renders_cache_hit_rate(self) -> None:
        node = AgentNode(
            agent_id="id", description="d", status="running",
            tokens=4010, messages=2,
            prompt_tokens=4000, completion_tokens=10, cached_tokens=3600,
        )
        assert node.usage == " (4000p, 10c, 3600cr, 90%cached, 2msgs)"

    def test_usage_omits_hit_rate_when_no_cached(self) -> None:
        node = AgentNode(
            agent_id="id", description="d", status="running",
            tokens=5010, messages=2,
            prompt_tokens=5000, completion_tokens=10, cached_tokens=0,
        )
        assert node.usage == " (5000p, 10c, 2msgs)"


class TestCacheHitRate:
    def test_zero_prompt_guards_to_zero(self) -> None:
        assert cache_hit_rate(0, 0) == 0.0
        assert cache_hit_rate(0, 100) == 0.0

    def test_full_hit_clamps_to_one(self) -> None:
        assert cache_hit_rate(4000, 4000) == 1.0
        assert cache_hit_rate(4000, 5000) == 1.0

    def test_partial_hit(self) -> None:
        assert cache_hit_rate(4000, 3000) == 0.75
        assert cache_hit_rate(1024, 102) == pytest.approx(0.099609375)


class TestBuildAgentTree:
    def test_empty_runtime(self, runtime) -> None:
        assert build_agent_tree(runtime) == []

    def test_single_root(self, runtime) -> None:
        ids = _seed(runtime, n=1)
        nodes = build_agent_tree(runtime)
        assert len(nodes) == 1
        assert nodes[0].agent_id == ids[0]
        assert nodes[0].description == "task-0"

    def test_nesting_via_parent(self, runtime) -> None:
        root_id = _seed(runtime, n=1)[0]
        root = runtime.get_agent(root_id)
        child = runtime.delegate(Task(description="sub 1"), parent=root)
        nodes = build_agent_tree(runtime)
        assert len(nodes) == 1
        assert [c.agent_id for c in nodes[0].children] == [child.id]

    def test_nested_grandchild(self, runtime) -> None:
        root_id = _seed(runtime, n=1)[0]
        root = runtime.get_agent(root_id)
        child = runtime.delegate(Task(description="sub 1"), parent=root)
        grand = runtime.delegate(Task(description="sub 2"), parent=child)
        nodes = build_agent_tree(runtime)
        assert nodes[0].children[0].children[0].agent_id == grand.id

    def test_orphans_without_root_are_skipped(self, runtime) -> None:
        stray = _seed(runtime, n=1)[0]
        runtime._task_graph.pop(stray)
        assert build_agent_tree(runtime) == []

    def test_status_reflects_task(self, runtime) -> None:
        aid = _seed(runtime, n=1)[0]
        runtime.get_agent(aid).task.status = TaskStatus.completed
        assert build_agent_tree(runtime)[0].status == "completed"

    def test_tokens_and_messages_come_from_tracker(self, runtime) -> None:
        aid = _seed(runtime, n=1)[0]
        asyncio.run(runtime.record_usage(aid, prompt_tokens=50, completion_tokens=50, message_count=4))
        agent = runtime.get_agent(aid)
        # Live context is separate and may be freed after completion; the
        # cumulative tracker count persists either way.
        agent.context.messages = [
            {"role": "user", "content": "start"},
            {"role": "assistant", "content": "ok"},
            {"role": "user", "content": "next"},
        ]
        node = build_agent_tree(runtime)[0]
        assert node.tokens == 100
        assert node.messages == 4

    def test_messages_persist_after_context_freed(self, runtime) -> None:
        aid = _seed(runtime, n=1)[0]
        asyncio.run(runtime.record_usage(aid, message_count=7))
        runtime.get_agent(aid).context.messages = []  # simulated _free_context()
        assert build_agent_tree(runtime)[0].messages == 7

    def test_cost_usd_from_prices(self, runtime) -> None:
        runtime.cost_policy.price_input_per_mtok = 0.1
        runtime.cost_policy.price_output_per_mtok = 0.3
        aid = _seed(runtime, n=1)[0]
        asyncio.run(runtime.record_usage(aid, prompt_tokens=1_000_000, completion_tokens=1_000_000))
        node = build_agent_tree(runtime)[0]
        assert node.cost_usd == pytest.approx(0.4)

    def test_provider_cost_preferred_over_estimate(self, runtime) -> None:
        runtime.cost_policy.price_input_per_mtok = 10.0  # absurd; ignored when provider reports
        aid = _seed(runtime, n=1)[0]
        asyncio.run(runtime.record_usage(aid, prompt_tokens=1000, cost=0.05))
        assert build_agent_tree(runtime)[0].cost_usd == pytest.approx(0.05)

    def test_cum_cost_includes_children(self, runtime) -> None:
        root_id = _seed(runtime, n=1)[0]
        root = runtime.get_agent(root_id)
        child = runtime.delegate(Task(description="child"), parent=root)
        grand = runtime.delegate(Task(description="grand"), parent=child)
        asyncio.run(runtime.record_usage(root_id, cost=0.01))
        asyncio.run(runtime.record_usage(child.id, cost=0.02))
        asyncio.run(runtime.record_usage(grand.id, cost=0.03))
        nodes = build_agent_tree(runtime)
        assert nodes[0].cost_usd == pytest.approx(0.01)
        assert nodes[0].cum_cost_usd == pytest.approx(0.06)
        assert nodes[0].children[0].cum_cost_usd == pytest.approx(0.05)
        assert nodes[0].children[0].children[0].cum_cost_usd == pytest.approx(0.03)

    def test_delegator_parent_shows_subtree_marker(self, runtime) -> None:
        root_id = _seed(runtime, n=1)[0]
        root = runtime.get_agent(root_id)
        child = runtime.delegate(Task(description="child"), parent=root)
        asyncio.run(runtime.record_usage(child.id, cost=0.04))
        node = build_agent_tree(runtime)[0]
        assert node.cost_usd == 0.0
        assert node.usage == " (Σ$0.0400)"

    def test_usage_renders_cost_marker(self) -> None:
        node = AgentNode(
            agent_id="id", description="d", status="running",
            tokens=1000, messages=1, cost_usd=0.05,
        )
        assert node.usage == " (1000t, 1msgs, $0.0500)"

    def test_usage_omits_zero_cost(self) -> None:
        node = AgentNode(agent_id="id", description="d", status="running", tokens=1000)
        assert node.usage == " (1000t)"

    def test_usage_shows_cumulative_subtree_cost(self) -> None:
        node = AgentNode(agent_id="id", description="d", status="running", cum_cost_usd=0.05)
        assert node.usage == " (Σ$0.0500)"

    def test_usage_omits_dup_cumulative_when_no_children(self) -> None:
        node = AgentNode(
            agent_id="id", description="d", status="running",
            tokens=100, cost_usd=0.05, cum_cost_usd=0.05,
        )
        assert node.usage == " (100t, $0.0500)"

    def test_fmt_usd_subcent_six_decimals(self) -> None:
        assert present.fmt_usd(0.00014) == "0.000140"

    def test_cache_hit_rate_property(self) -> None:
        node = AgentNode(
            agent_id="id", description="d", status="running",
            prompt_tokens=4000, cached_tokens=1000,
        )
        assert node.cache_hit_rate == 0.25


class TestBuildStats:
    def test_zero_state(self, runtime) -> None:
        s = build_stats(runtime)
        assert s.agents == 0
        assert s.commits == 0
        assert s.tokens == 0
        assert s.prompt_tokens == 0
        assert s.cached_tokens == 0
        assert s.cache_hit_rate == 0.0
        assert s.cost_usd == 0.0

    def test_aggregates(self, runtime) -> None:
        _seed(runtime, n=3)
        assert build_stats(runtime).agents == 3

    def test_tokens_accumulate(self, runtime) -> None:
        aid = _seed(runtime, n=1)[0]
        asyncio.run(runtime.record_usage(aid, prompt_tokens=10))
        assert build_stats(runtime).tokens == 10

    def test_cache_fields_reflect_tracker(self, runtime) -> None:
        aid = _seed(runtime, n=1)[0]
        asyncio.run(runtime.record_usage(
            aid, prompt_tokens=4000, completion_tokens=10, cached_tokens=3000, message_count=2,
        ))
        s = build_stats(runtime)
        assert s.prompt_tokens == 4000
        assert s.cached_tokens == 3000
        assert s.cache_hit_rate == 0.75

    def test_cache_hit_rate_aggregates_across_agents(self, runtime) -> None:
        a = _seed(runtime, n=1)[0]
        b = _seed(runtime, n=1)[0]
        asyncio.run(runtime.record_usage(
            a, prompt_tokens=4000, cached_tokens=4000, message_count=1,
        ))
        asyncio.run(runtime.record_usage(
            b, prompt_tokens=1000, cached_tokens=0, message_count=1,
        ))
        s = build_stats(runtime)
        assert s.prompt_tokens == 5000
        assert s.cached_tokens == 4000
        assert s.cache_hit_rate == 0.8

    def test_cost_usd_aggregates(self, runtime) -> None:
        runtime.cost_policy.price_input_per_mtok = 0.5
        a = _seed(runtime, n=1)[0]
        asyncio.run(runtime.record_usage(a, prompt_tokens=1_000_000))
        assert build_stats(runtime).cost_usd == pytest.approx(0.5)

    def test_stats_cost_prefers_provider_reported(self, runtime) -> None:
        runtime.cost_policy.price_input_per_mtok = 10.0
        a = _seed(runtime, n=1)[0]
        asyncio.run(runtime.record_usage(a, prompt_tokens=1000, cost=0.07))
        assert build_stats(runtime).cost_usd == pytest.approx(0.07)


def test_present_has_no_textual_dependency() -> None:
    src = inspect.getsource(present)
    assert "textual" not in src.lower()
    assert "rich" not in src.lower()