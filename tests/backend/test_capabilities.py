from __future__ import annotations

from pathlib import Path

import pytest

from dynamic_harness.core.tools import ToolDef, ToolRegistry
from dynamic_harness.core.tools.agents import TOOL_ASK_DEF
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import Task, TaskStatus
from dynamic_harness.core.agent import Agent


def test_tool_registry_register_and_list() -> None:
    reg = ToolRegistry()
    reg.register(ToolDef(name="test", description="A test tool", input_schema={"type": "object", "properties": {}}), lambda: "ok")
    assert "test" in reg.list_tools()


def test_tool_registry_schemas() -> None:
    reg = ToolRegistry()
    reg.register(ToolDef(name="foo", description="Foo tool", input_schema={"type": "object", "properties": {}}), lambda: "ok")
    schemas = reg.openai_schemas()
    assert len(schemas) == 1
    assert schemas[0]["function"]["name"] == "foo"
    assert schemas[0]["type"] == "function"


@pytest.mark.asyncio
async def test_tool_registry_execute_known(runtime: Runtime) -> None:
    agent = runtime.delegate(Task(description="test"))
    result = await runtime.tool_registry.execute("glob", "tc1", agent=agent, pattern="*.py")
    assert "Error" not in result.content
    assert "tc1" == result.tool_call_id


@pytest.mark.asyncio
async def test_tool_registry_execute_unknown(runtime: Runtime) -> None:
    agent = runtime.delegate(Task(description="test"))
    result = await runtime.tool_registry.execute("nonexistent", "tc1", agent=agent)
    assert "Error" in result.content


@pytest.mark.asyncio
async def test_tool_registry_execute_failure(runtime: Runtime) -> None:
    reg = ToolRegistry()
    async def failing_fn(**kwargs: object) -> str:
        raise ValueError("boom")

    reg.register(ToolDef(name="crash", description="crash", input_schema={"type": "object", "properties": {}}), failing_fn)
    agent = runtime.delegate(Task(description="test"))
    result = await reg.execute("crash", "tc1", agent=agent)
    assert "Error executing crash" in result.content
    assert "boom" in result.content


@pytest.mark.asyncio
async def test_delegate_tool_creates_and_runs_child(runtime: Runtime) -> None:
    agent = runtime.delegate(Task(description="parent"))
    result = await runtime.tool_registry.execute("delegate", "tc1", agent=agent, description="child task")
    import json
    data = json.loads(result.content)
    assert data["status"] == "failed"
    assert "failure" in data
    assert runtime.agent_count() == 2


@pytest.mark.asyncio
async def test_write_and_read_tool_roundtrip(runtime: Runtime) -> None:
    agent = runtime.delegate(Task(description="test"))
    fname = "test.txt"
    write_result = await runtime.tool_registry.execute("write", "tc1", agent=agent, path=fname, content="hello")
    assert "Wrote" in write_result.content
    read_result = await runtime.tool_registry.execute("read", "tc2", agent=agent, path=fname)
    assert read_result.content == "hello"


@pytest.mark.asyncio
async def test_edit_tool(runtime: Runtime) -> None:
    agent = runtime.delegate(Task(description="test"))
    fname = "edit.txt"
    await runtime.tool_registry.execute("write", "tc0", agent=agent, path=fname, content="foo bar baz")
    result = await runtime.tool_registry.execute("edit", "tc1", agent=agent, path=fname, old_string="bar", new_string="qux")
    assert "Replaced" in result.content
    read_result = await runtime.tool_registry.execute("read", "tc2", agent=agent, path=fname)
    assert read_result.content == "foo qux baz"


def test_ask_tool_def_in_registry(runtime: Runtime) -> None:
    tools = runtime.tool_registry.list_tools()
    assert "ask" in tools
    td, fn = runtime.tool_registry.get("ask")
    assert td.name == "ask"
    assert "question" in td.input_schema.get("properties", {})


def test_default_tools_all_seventeen(runtime: Runtime) -> None:
    expected = {"read", "write", "glob", "grep", "bash", "webfetch", "edit", "delegate", "report", "escalate", "fail", "ask", "compress", "prune", "restore", "converse", "read_artifact"}
    assert set(runtime.tool_registry.list_tools()) == expected


@pytest.mark.asyncio
async def test_glob_skips_hidden_files(runtime: Runtime, tmp_path: Path) -> None:
    agent = runtime.delegate(Task(description="test"))
    (tmp_path / "visible.txt").write_text("visible")
    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / "secret.txt").write_text("secret")
    result = await runtime.tool_registry.execute("glob", "tc1", agent=agent, pattern=str(tmp_path / "**/*"))
    assert "visible.txt" in result.content
    assert ".hidden" not in result.content
    assert "secret.txt" not in result.content


@pytest.mark.asyncio
async def test_glob_skips_dotfiles(runtime: Runtime, tmp_path: Path) -> None:
    agent = runtime.delegate(Task(description="test"))
    (tmp_path / "visible.txt").write_text("visible")
    (tmp_path / ".dotfile").write_text("dot")
    result = await runtime.tool_registry.execute("glob", "tc1", agent=agent, pattern=str(tmp_path / "*"))
    assert "visible.txt" in result.content
    assert ".dotfile" not in result.content


@pytest.mark.asyncio
async def test_glob_skips_deeply_nested_hidden(runtime: Runtime, tmp_path: Path) -> None:
    agent = runtime.delegate(Task(description="test"))
    nested_dir = tmp_path / "a" / "b" / ".hidden" / "c"
    nested_dir.mkdir(parents=True)
    (nested_dir / "deep.txt").write_text("deep")
    (tmp_path / "a" / "visible.txt").write_text("visible")
    result = await runtime.tool_registry.execute("glob", "tc1", agent=agent, pattern=str(tmp_path / "**/*"))
    assert "visible.txt" in result.content
    assert ".hidden" not in result.content
    assert "deep.txt" not in result.content


@pytest.mark.asyncio
async def test_grep_skips_hidden_files(runtime: Runtime, tmp_path: Path) -> None:
    agent = runtime.delegate(Task(description="test"))
    (tmp_path / "visible.txt").write_text("needle")
    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / "secret.txt").write_text("needle")
    result = await runtime.tool_registry.execute("grep", "tc1", agent=agent, pattern="needle", path=str(tmp_path))
    assert "visible.txt" in result.content
    assert ".hidden" not in result.content
    assert "secret.txt" not in result.content


@pytest.mark.asyncio
async def test_grep_skips_dotfiles(runtime: Runtime, tmp_path: Path) -> None:
    agent = runtime.delegate(Task(description="test"))
    (tmp_path / "visible.txt").write_text("needle")
    (tmp_path / ".dotfile").write_text("needle")
    result = await runtime.tool_registry.execute("grep", "tc1", agent=agent, pattern="needle", path=str(tmp_path))
    assert "visible.txt" in result.content
    assert ".dotfile" not in result.content


@pytest.mark.asyncio
async def test_grep_finds_nothing_in_all_hidden(runtime: Runtime, tmp_path: Path) -> None:
    agent = runtime.delegate(Task(description="test"))
    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / "secret.txt").write_text("needle")
    result = await runtime.tool_registry.execute("grep", "tc1", agent=agent, pattern="needle", path=str(tmp_path))
    assert result.content == "No matches found"


@pytest.mark.asyncio
async def test_escalate_tool_sets_status(runtime: Runtime) -> None:
    agent = runtime.delegate(Task(description="test"))
    result = await runtime.tool_registry.execute("escalate", "tc1", agent=agent, issue="critical bug")
    assert "Escalated" in result.content
    assert agent.task.status.value == "escalated"


@pytest.mark.asyncio
async def test_fail_tool_sets_status(runtime: Runtime) -> None:
    agent = runtime.delegate(Task(description="test"))
    result = await runtime.tool_registry.execute("fail", "tc1", agent=agent, error="catastrophic error")
    assert "Failed" in result.content
    assert agent.task.status.value == "failed"


@pytest.mark.asyncio
async def test_report_tool_sets_status(runtime: Runtime) -> None:
    agent = runtime.delegate(Task(description="test"))
    result = await runtime.tool_registry.execute("report", "tc1", agent=agent, summary="all done")
    assert "Reported" in result.content
    assert agent.task.status.value == "completed"


@pytest.mark.asyncio
async def test_converse_tool_nonexistent_agent(runtime: Runtime) -> None:
    agent = runtime.delegate(Task(description="test"))
    result = await runtime.tool_registry.execute("converse", "tc1", agent=agent, agent_id="nonexistent", message="hello")
    assert "no agent found" in result.content


@pytest.mark.asyncio
async def test_converse_tool_wrong_status(runtime: Runtime) -> None:
    agent = runtime.delegate(Task(description="test"))
    target = runtime.delegate(Task(description="target"))
    target.task.status = TaskStatus("failed")
    result = await runtime.tool_registry.execute("converse", "tc1", agent=agent, agent_id=target.id, message="hello")
    assert "cannot converse" in result.content


@pytest.mark.asyncio
async def test_compress_tool_nothing_to_compress(runtime: Runtime) -> None:
    agent = runtime.delegate(Task(description="test"))
    result = await runtime.tool_registry.execute("compress", "tc1", agent=agent)
    assert "Nothing to compress" in result.content


@pytest.mark.asyncio
async def test_compress_tool_no_llm(runtime: Runtime) -> None:
    agent = runtime.delegate(Task(description="test"))
    agent._messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "question"},
        {"role": "assistant", "content": "answer"},
    ]
    result = await runtime.tool_registry.execute("compress", "tc1", agent=agent)
    assert "No LLM available" in result.content


def _commit_turn(agent: Agent, *, tools: bool = True, content: str = "reasoning") -> None:
    assistant_msg: dict[str, object] = {
        "role": "assistant",
        "content": content,
    }
    results: list[dict[str, object]] = []
    if tools:
        assistant_msg["tool_calls"] = [
            {"id": f"call_{agent._turn_counter}", "type": "function", "function": {"name": "bash", "arguments": "{}"}},
        ]
        results.append({"role": "tool", "tool_call_id": f"call_{agent._turn_counter}", "content": "output of a tool call"})
    agent._commit_turn(assistant_msg, results)


@pytest.mark.asyncio
async def test_prune_removes_turn_and_leaves_marker(runtime: Runtime) -> None:
    agent = runtime.delegate(Task(description="test"))
    _commit_turn(agent)
    _commit_turn(agent)
    assert len(agent._messages) == 4

    result = await runtime.tool_registry.execute("prune", "tc1", agent=agent, prune_ids=["t0"])
    assert "t0" in result.content
    assert agent._pruned == {"t0"}
    assert len(agent._messages) == 3
    assert any("PRUNED t0" in str(m.get("content")) for m in agent._messages)
    assert len(agent._turns["t0"]) == 2


@pytest.mark.asyncio
async def test_prune_is_pair_atomic_no_dangling_tool_results(runtime: Runtime) -> None:
    agent = runtime.delegate(Task(description="test"))
    _commit_turn(agent)
    _commit_turn(agent)
    await runtime.tool_registry.execute("prune", "tc1", agent=agent, prune_ids=["t0"])

    live_ids = set()
    for m in agent._messages:
        for tc in m.get("tool_calls") or []:
            live_ids.add(tc["id"])
    dangling = [m["tool_call_id"] for m in agent._messages if m.get("role") == "tool" and m["tool_call_id"] not in live_ids]
    assert dangling == []


@pytest.mark.asyncio
async def test_prune_rejects_invalid_id(runtime: Runtime) -> None:
    agent = runtime.delegate(Task(description="test"))
    _commit_turn(agent)
    result = await runtime.tool_registry.execute("prune", "tc1", agent=agent, prune_ids=["t0", "t99"])
    assert "unknown ids" in result.content and "t99" in result.content
    assert "t0" in result.content


@pytest.mark.asyncio
async def test_prune_empty_list_returns_guidance(runtime: Runtime) -> None:
    agent = runtime.delegate(Task(description="test"))
    _commit_turn(agent)
    result = await runtime.tool_registry.execute("prune", "tc1", agent=agent, prune_ids=[])
    assert "prune(prune_ids=[...])" in result.content


@pytest.mark.asyncio
async def test_restore_returns_pruned_turn(runtime: Runtime) -> None:
    agent = runtime.delegate(Task(description="test"))
    _commit_turn(agent)
    _commit_turn(agent)
    await runtime.tool_registry.execute("prune", "tc1", agent=agent, prune_ids=["t0"])
    assert len(agent._messages) == 3

    result = await runtime.tool_registry.execute("restore", "tc2", agent=agent, prune_id="t0")
    assert "Restored turn t0" in result.content
    assert "t0" not in agent._pruned
    assert len(agent._messages) == 4
    assert all(not ("PRUNED t0" in str(m.get("content"))) for m in agent._messages)
    assert len(agent._turns["t0"]) == 2


@pytest.mark.asyncio
async def test_restore_unknown_or_active_id(runtime: Runtime) -> None:
    agent = runtime.delegate(Task(description="test"))
    _commit_turn(agent)
    result = await runtime.tool_registry.execute("restore", "tc1", agent=agent, prune_id="t0")
    assert "not currently pruned" in result.content
    result = await runtime.tool_registry.execute("restore", "tc2", agent=agent, prune_id="nope")
    assert "not currently pruned" in result.content


@pytest.mark.asyncio
async def test_prune_accepts_single_string_input(runtime: Runtime) -> None:
    agent = runtime.delegate(Task(description="test"))
    _commit_turn(agent)
    result = await runtime.tool_registry.execute("prune", "tc1", agent=agent, prune_ids="t0")
    assert "t0" in result.content
    assert agent._pruned == {"t0"}


@pytest.mark.asyncio
async def test_restore_errors_when_marker_missing(runtime: Runtime) -> None:
    agent = runtime.delegate(Task(description="test"))
    _commit_turn(agent)
    _commit_turn(agent)
    await runtime.tool_registry.execute("prune", "tc1", agent=agent, prune_ids=["t0"])
    agent._messages = [m for m in agent._messages if not str(m.get("content", "")).startswith("[PRUNED")]
    assert len(agent._messages) == 2

    result = await runtime.tool_registry.execute("restore", "tc2", agent=agent, prune_id="t0")
    assert "no longer present" in result.content
    assert "t0" in agent._pruned
    assert len(agent._messages) == 2


@pytest.mark.asyncio
async def test_prune_evicts_old_retained_turns_at_cap(runtime: Runtime) -> None:
    agent = runtime.delegate(Task(description="test"))
    agent.max_pruned_retained = 2
    for _ in range(4):
        _commit_turn(agent)
    await runtime.tool_registry.execute("prune", "tc1", agent=agent, prune_ids=["t0", "t1", "t2", "t3"])

    assert len(agent._pruned) <= 2
    assert "t0" not in agent._pruned
    assert "t0" not in agent._turns
    assert "t0" not in agent._prune_markers
    assert "t3" in agent._pruned
    assert "t3" in agent._turns


@pytest.mark.asyncio
async def test_restore_uses_stored_index_reorders_markers(runtime: Runtime) -> None:
    agent = runtime.delegate(Task(description="test"))
    for _ in range(3):
        _commit_turn(agent)
    await runtime.tool_registry.execute("prune", "tc1", agent=agent, prune_ids=["t0"])
    await runtime.tool_registry.execute("prune", "tc2", agent=agent, prune_ids=["t1"])

    order = [str(m.get("content", "")) for m in agent._messages if str(m.get("content", "")).startswith("[PRUNED")]
    assert order[0].startswith("[PRUNED t0")
    assert order[1].startswith("[PRUNED t1")

    await runtime.tool_registry.execute("restore", "tc3", agent=agent, prune_id="t0")

    order = [str(m.get("content", "")) for m in agent._messages if str(m.get("content", "")).startswith("[PRUNED")]
    assert len(order) == 1
    assert order[0].startswith("[PRUNED t1")
    assert "t0" not in agent._pruned
    assert "t1" in agent._pruned


def test_active_turn_window_is_configurable(tmp: Path) -> None:
    rt = Runtime(artifact_root=tmp / "a", repo_root=tmp / "r", generated_root=tmp)
    agent = Agent("a", Task(description="test"), rt, active_turn_window=200)
    assert agent.active_turn_window == 200
    assert rt.delegate(Task(description="test")).active_turn_window == 50


@pytest.mark.asyncio
async def test_bash_executes_simple_command(runtime: Runtime) -> None:
    agent = runtime.delegate(Task(description="test"))
    result = await runtime.tool_registry.execute("bash", "tc1", agent=agent, command="echo hello")
    assert "hello" in result.content


@pytest.mark.asyncio
async def test_bash_empty_output(runtime: Runtime) -> None:
    agent = runtime.delegate(Task(description="test"))
    result = await runtime.tool_registry.execute("bash", "tc1", agent=agent, command="true")
    assert "(no output)" in result.content


@pytest.mark.asyncio
async def test_bash_stderr_output(runtime: Runtime) -> None:
    agent = runtime.delegate(Task(description="test"))
    result = await runtime.tool_registry.execute("bash", "tc1", agent=agent, command="python3 -c 'import sys; print(\"out\"); print(\"err\", file=sys.stderr)'")
    assert "out" in result.content
    assert "(STDERR)" in result.content
    assert "err" in result.content


@pytest.mark.asyncio
async def test_bash_invalid_syntax(runtime: Runtime) -> None:
    agent = runtime.delegate(Task(description="test"))
    result = await runtime.tool_registry.execute("bash", "tc1", agent=agent, command="echo 'unclosed")
    assert "Error" in result.content
    assert "invalid command syntax" in result.content


@pytest.mark.asyncio
async def test_bash_command_not_found(runtime: Runtime) -> None:
    agent = runtime.delegate(Task(description="test"))
    result = await runtime.tool_registry.execute("bash", "tc1", agent=agent, command="nonexistent_command_xyz")
    assert "Error executing bash" in result.content


@pytest.mark.asyncio
async def test_bash_timeout(runtime: Runtime) -> None:
    agent = runtime.delegate(Task(description="test"))
    result = await runtime.tool_registry.execute("bash", "tc1", agent=agent, command="sleep 5", timeout=100)
    assert "timed out" in result.content


@pytest.mark.asyncio
async def test_grep_reports_unreadable_files(runtime: Runtime, tmp_path: Path) -> None:
    agent = runtime.delegate(Task(description="test"))
    (tmp_path / "readable.txt").write_text("needle")
    result = await runtime.tool_registry.execute("grep", "tc1", agent=agent, pattern="needle", path=str(tmp_path))
    assert "needle" in result.content


@pytest.mark.asyncio
async def test_read_artifact_tool(runtime: Runtime) -> None:
    agent = runtime.delegate(Task(description="test"))
    agent.report = lambda payload: runtime.deliver_report(agent.id, payload)
    result = await runtime.tool_registry.execute("report", "tc1", agent=agent, summary="artifact test report")
    commits = runtime.repository.log()
    assert len(commits) > 0
    artifact_id = commits[0].artifact_ids[-1]
    result2 = await runtime.tool_registry.execute("read_artifact", "tc2", agent=agent, artifact_id=artifact_id)
    assert "artifact test report" in result2.content
