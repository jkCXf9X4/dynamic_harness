from __future__ import annotations

import asyncio
import inspect

from dynamic_harness.cli import present
from dynamic_harness.cli.present import AgentNode, build_agent_tree, build_stats
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

    def test_usage_comes_from_tracker(self, runtime) -> None:
        aid = _seed(runtime, n=1)[0]
        asyncio.run(runtime.record_usage(aid, prompt_tokens=50, completion_tokens=50, message_count=4))
        node = build_agent_tree(runtime)[0]
        assert node.tokens == 100
        assert node.messages == 4


class TestBuildStats:
    def test_zero_state(self, runtime) -> None:
        s = build_stats(runtime)
        assert s.agents == 0
        assert s.commits == 0
        assert s.tokens == 0

    def test_aggregates(self, runtime) -> None:
        _seed(runtime, n=3)
        assert build_stats(runtime).agents == 3

    def test_tokens_accumulate(self, runtime) -> None:
        aid = _seed(runtime, n=1)[0]
        asyncio.run(runtime.record_usage(aid, prompt_tokens=10))
        assert build_stats(runtime).tokens == 10


def test_present_has_no_textual_dependency() -> None:
    src = inspect.getsource(present)
    assert "textual" not in src.lower()
    assert "rich" not in src.lower()