from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from dynamic_harness.core.agent import Agent
from dynamic_harness.core.capabilities import TOOL_ASK_DEF, ToolDef, ToolRegistry
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import Task


@pytest.fixture
def runtime() -> Runtime:
    tmp = Path(tempfile.mkdtemp())
    return Runtime(artifact_root=tmp / "artifacts", repo_root=tmp / "repo")


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
    agent = runtime.spawn_agent(Task(description="test"))
    result = await runtime.tool_registry.execute("glob", "tc1", agent=agent, pattern="*.py")
    assert "Error" not in result.content
    assert "tc1" == result.tool_call_id


@pytest.mark.asyncio
async def test_tool_registry_execute_unknown(runtime: Runtime) -> None:
    agent = runtime.spawn_agent(Task(description="test"))
    result = await runtime.tool_registry.execute("nonexistent", "tc1", agent=agent)
    assert "Error" in result.content


@pytest.mark.asyncio
async def test_tool_registry_execute_failure(runtime: Runtime) -> None:
    reg = ToolRegistry()
    async def failing_fn(**kwargs: object) -> str:
        raise ValueError("boom")

    reg.register(ToolDef(name="crash", description="crash", input_schema={"type": "object", "properties": {}}), failing_fn)
    agent = runtime.spawn_agent(Task(description="test"))
    result = await reg.execute("crash", "tc1", agent=agent)
    assert "Error executing crash" in result.content
    assert "boom" in result.content


@pytest.mark.asyncio
async def test_spawn_tool_creates_and_runs_child(runtime: Runtime) -> None:
    agent = runtime.spawn_agent(Task(description="parent"))
    result = await runtime.tool_registry.execute("spawn", "tc1", agent=agent, description="child task")
    assert "Spawned agent" in result.content
    assert "Status: completed" in result.content
    assert runtime.agent_count() == 2


@pytest.mark.asyncio
async def test_write_and_read_tool_roundtrip(runtime: Runtime, tmp_path: Path) -> None:
    agent = runtime.spawn_agent(Task(description="test"))
    fpath = str(tmp_path / "test.txt")
    write_result = await runtime.tool_registry.execute("write", "tc1", agent=agent, path=fpath, content="hello")
    assert "Wrote" in write_result.content
    read_result = await runtime.tool_registry.execute("read", "tc2", agent=agent, path=fpath)
    assert read_result.content == "hello"


@pytest.mark.asyncio
async def test_edit_tool(runtime: Runtime, tmp_path: Path) -> None:
    agent = runtime.spawn_agent(Task(description="test"))
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
    expected = {"read", "write", "glob", "grep", "bash", "webfetch", "edit", "spawn", "report", "escalate", "fail", "ask", "compress", "converse", "read_artifact"}
    assert set(runtime.tool_registry.list_tools()) == expected