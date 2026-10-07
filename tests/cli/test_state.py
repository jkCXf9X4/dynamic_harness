from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from dynamic_harness.cli.state import StateWriter, attach_events, _node_dict
from dynamic_harness.cli.present import (
    AgentNode,
    build_agent_tree,
    fmt_age,
    render_text_tree,
)
from dynamic_harness.core.task import ActivityEvent, ActivityEventType, ReportPayload, Task


def test_append_event_writes_json_l(tmp_path):
    w = StateWriter(tmp_path)
    w.append_event({"event": "task", "agent_id": "abc"})
    parsed = json.loads(tmp_path.joinpath("events.jsonl").read_text().strip())
    assert parsed["event"] == "task"
    assert parsed["agent_id"] == "abc"
    assert "ts" in parsed


def test_snapshot_writes_tree_and_stats_empty(runtime, tmp_path):
    w = StateWriter(tmp_path)
    w.snapshot(runtime)
    assert json.loads(w.tree_path.read_text()) == []
    raw = json.loads(w.stats_path.read_text())
    assert raw["generated_at"].startswith("20")  # ISO timestamp of the write
    raw.pop("generated_at")
    assert raw == {
        "agents": 0, "commits": 0, "tokens": 0,
        "prompt_tokens": 0, "cached_tokens": 0, "cache_hit_rate": 0.0,
        "cost_usd": 0.0,
    }


def test_snapshot_includes_nested_agents(runtime, tmp_path):
    root = runtime.delegate(Task(description="root"))
    child = runtime.delegate(Task(description="child"), parent=root)
    w = StateWriter(tmp_path)
    w.snapshot(runtime)
    tree = json.loads(w.tree_path.read_text())
    assert tree[0]["description"] == "root"
    assert tree[0]["children"][0]["agent_id"] == child.id


def test_node_dict_is_json_serializable():
    node = AgentNode(
        agent_id="id", description="desc", status="running",
        children=[AgentNode(agent_id="c", description="x", status="done")],
    )
    assert json.loads(json.dumps(_node_dict(node)))["children"][0]["status"] == "done"


def test_node_dict_includes_cache_hit_rate():
    node = AgentNode(
        agent_id="id", description="desc", status="running",
        prompt_tokens=4000, cached_tokens=3000,
    )
    d = _node_dict(node)
    assert d["prompt_tokens"] == 4000
    assert d["cached_tokens"] == 3000
    assert d["cache_hit_rate"] == 0.75


def test_node_dict_includes_cost_usd():
    node = AgentNode(
        agent_id="id", description="desc", status="running",
        cost_usd=0.0012, cum_cost_usd=0.0034,
    )
    d = _node_dict(node)
    assert d["cost_usd"] == 0.0012
    assert d["cum_cost_usd"] == 0.0034


def test_snapshot_stats_includes_cache_fields(runtime, tmp_path):
    import asyncio

    agent = runtime.delegate(Task(description="t"))
    asyncio.run(runtime.record_usage(
        agent.id, prompt_tokens=2000, completion_tokens=10, cached_tokens=500, message_count=1,
    ))
    w = StateWriter(tmp_path)
    w.snapshot(runtime)
    stats = json.loads(w.stats_path.read_text())
    assert stats["agents"] == 1
    assert stats["prompt_tokens"] == 2000
    assert stats["cached_tokens"] == 500
    assert stats["cache_hit_rate"] == 0.25


def test_attach_logs_report_and_activity(runtime, tmp_path):
    w = StateWriter(tmp_path)
    attach_events(runtime, w)
    agent = runtime.delegate(Task(description="t"))
    runtime.deliver_report(agent.id, ReportPayload(task_id=agent.task.id, summary="hi"))
    runtime.emit_activity(ActivityEvent(agent_id=agent.id, event_type=ActivityEventType.ITERATION))
    payload = tmp_path.joinpath("events.jsonl").read_text().splitlines()
    kinds = {json.loads(line)["event"] for line in payload}
    assert {"report", "activity"} <= kinds


def test_terminal_report_snapshot_refreshes_tree(runtime, tmp_path):
    w = StateWriter(tmp_path)
    attach_events(runtime, w)
    w.tree_path.unlink()
    agent = runtime.delegate(Task(description="done"))
    runtime.deliver_report(agent.id, ReportPayload(task_id=agent.task.id, summary="s"))
    assert w.tree_path.exists()


def test_snapshot_throttles_non_forced_calls(runtime, tmp_path):
    w = StateWriter(tmp_path, snapshot_interval=3600.0)
    w.snapshot(runtime)
    first = w.tree_path.read_text()
    w.tree_path.write_text("stale")
    w.snapshot(runtime)  # within interval -> throttled, no rewrite
    assert w.tree_path.read_text() == "stale"
    w.snapshot(runtime, force=True)  # terminal event -> forced flush
    assert w.tree_path.read_text() == first


def test_activity_event_refreshes_tree_throttled(runtime, tmp_path):
    w = StateWriter(tmp_path, snapshot_interval=0.0)
    attach_events(runtime, w)
    w.tree_path.unlink()
    agent = runtime.delegate(Task(description="working"))
    runtime.emit_activity(ActivityEvent(agent_id=agent.id, event_type=ActivityEventType.ITERATION))
    assert w.tree_path.exists()


def test_snapshot_writes_agents_txt(runtime, tmp_path):
    root = runtime.delegate(Task(description="root task"))
    runtime.delegate(Task(description="child task"), parent=root)
    w = StateWriter(tmp_path)
    w.snapshot(runtime)
    txt = tmp_path.joinpath("agents.txt").read_text()
    assert "root task" in txt
    assert "child task" in txt
    assert "running" in txt


def test_render_text_tree_empty():
    assert render_text_tree([]) == "(no agents)\n"


def test_render_text_tree_flat_and_nested():
    root = AgentNode(
        agent_id="a" * 12, description="root", status="completed", tokens=100, messages=3,
        children=[
            AgentNode(agent_id="c" * 12, description="child1", status="running"),
            AgentNode(agent_id="d" * 12, description="child2", status="pending"),
        ],
    )
    tree = render_text_tree([root])
    lines = tree.splitlines()
    assert len(lines) == 3
    assert "a" * 8 in lines[0]  # short_id clipped to 8
    assert "[completed]" in lines[0]
    assert "(3msgs, 100t)" in lines[0]
    assert "├" in lines[1] and "└" in lines[2]  # branch across two siblings


def test_fmt_age():
    assert fmt_age(12) == "12s"
    assert fmt_age(135) == "2m15s"
    assert fmt_age(-3) == "0s"


def test_render_text_tree_shows_activity_age():
    node = AgentNode(
        agent_id="a" * 12, description="d", status="running",
        activity="tool echo", activity_age_s=12.0,
    )
    assert "(tool echo 12s)" in render_text_tree([node])


def test_node_dict_includes_activity():
    node = AgentNode(
        agent_id="id", description="desc", status="running",
        activity="tool echo", activity_age_s=5.0,
    )
    d = _node_dict(node)
    assert d["activity"] == "tool echo"
    assert d["activity_age_s"] == 5.0


def test_agents_txt_has_generated_header(runtime, tmp_path):
    runtime.delegate(Task(description="root task"))
    w = StateWriter(tmp_path)
    w.snapshot(runtime)
    first = tmp_path.joinpath("agents.txt").read_text().splitlines()[0]
    assert first.startswith("# generated 2")
    assert "1 agents" in first


def test_flush_bypasses_throttle(runtime, tmp_path):
    w = StateWriter(tmp_path, snapshot_interval=3600.0)
    w.snapshot(runtime)
    tmp_path.joinpath("agents.txt").write_text("stale")
    w.flush(runtime)  # heartbeat path: rate-limits itself, no throttle
    assert tmp_path.joinpath("agents.txt").read_text() != "stale"


def test_activity_age_rendered_for_running_agent(runtime, tmp_path):
    w = StateWriter(tmp_path)
    attach_events(runtime, w)
    agent = runtime.delegate(Task(description="working"))
    runtime.emit_activity(ActivityEvent(
        agent_id=agent.id,
        event_type=ActivityEventType.ITERATION,
        data={"turn": 2},
        timestamp=datetime.now(timezone.utc) - timedelta(seconds=90),
    ))
    w.snapshot(runtime, force=True)
    txt = tmp_path.joinpath("agents.txt").read_text()
    assert "(turn 2 1m30s)" in txt


def test_activity_age_hidden_for_terminal_agent(runtime, tmp_path):
    w = StateWriter(tmp_path)
    attach_events(runtime, w)
    agent = runtime.delegate(Task(description="done"))
    runtime.emit_activity(ActivityEvent(
        agent_id=agent.id, event_type=ActivityEventType.ITERATION,
    ))
    runtime.deliver_report(agent.id, ReportPayload(task_id=agent.task.id, summary="s"))
    w.snapshot(runtime, force=True)
    txt = tmp_path.joinpath("agents.txt").read_text()
    assert "[completed]" in txt
    assert "(turn" not in txt