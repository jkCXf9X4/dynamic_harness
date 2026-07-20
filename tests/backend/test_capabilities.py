from __future__ import annotations

from pathlib import Path

import pytest

from dynamic_harness.core.capabilities import TOOL_ASK_DEF, ToolDef, ToolRegistry
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import Task


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
    assert "Delegated to agent" in result.content
    assert "Status: completed" in result.content
    assert runtime.agent_count() == 2


@pytest.mark.asyncio
async def test_write_and_read_tool_roundtrip(runtime: Runtime, tmp_path: Path) -> None:
    agent = runtime.delegate(Task(description="test"))
    fpath = str(tmp_path / "test.txt")
    write_result = await runtime.tool_registry.execute("write", "tc1", agent=agent, path=fpath, content="hello")
    assert "Wrote" in write_result.content
    read_result = await runtime.tool_registry.execute("read", "tc2", agent=agent, path=fpath)
    assert read_result.content == "hello"


@pytest.mark.asyncio
async def test_edit_tool(runtime: Runtime, tmp_path: Path) -> None:
    agent = runtime.delegate(Task(description="test"))
    fpath = str(tmp_path / "edit.txt")
    (tmp_path / "edit.txt").write_text("foo bar baz")
    result = await runtime.tool_registry.execute("edit", "tc1", agent=agent, path=fpath, old_string="bar", new_string="qux")
    assert "Replaced" in result.content
    assert (tmp_path / "edit.txt").read_text() == "foo qux baz"


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
