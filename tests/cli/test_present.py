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

    def test_tokens_come_from_tracker_messages_from_live_context(self, runtime) -> None:
        aid = _seed(runtime, n=1)[0]
        asyncio.run(runtime.record_usage(aid, prompt_tokens=50, completion_tokens=50, message_count=4))
        agent = runtime.get_agent(aid)
        agent.context.messages = [
            {"role": "user", "content": "start"},
            {"role": "assistant", "content": "ok"},
            {"role": "user", "content": "next"},
        ]
        node = build_agent_tree(runtime)[0]
        assert node.tokens == 100
        assert node.messages == 3

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


def test_present_has_no_textual_dependency() -> None:
    src = inspect.getsource(present)
    assert "textual" not in src.lower()
    assert "rich" not in src.lower()