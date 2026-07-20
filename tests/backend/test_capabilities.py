from __future__ import annotations

from pathlib import Path

import pytest

from dynamic_harness.core.capabilities import TOOL_ASK_DEF, ToolDef, ToolRegistry
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import Task, TaskStatus


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


def test_default_tools_all_fifteen(runtime: Runtime) -> None:
    expected = {"read", "write", "glob", "grep", "bash", "webfetch", "edit", "delegate", "report", "escalate", "fail", "ask", "compress", "converse", "read_artifact"}
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
