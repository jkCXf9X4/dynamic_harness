from __future__ import annotations

import json

from dynamic_harness.cli.state import StateWriter, attach_events, _node_dict
from dynamic_harness.cli.present import (
    AgentNode,
    build_agent_tree,
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
    assert json.loads(w.stats_path.read_text()) == {"agents": 0, "commits": 0, "tokens": 0}


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
    assert "(100t, 3msgs)" in lines[0]
    assert "├" in lines[1] and "└" in lines[2]  # branch across two siblings