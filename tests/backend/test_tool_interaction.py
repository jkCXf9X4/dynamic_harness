from __future__ import annotations

import json
import shutil
from collections.abc import AsyncGenerator

import pytest

from dynamic_harness.core.agent import Agent
from dynamic_harness.core.capabilities import ToolDef, ToolRegistry
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import Task, TaskStatus
from dynamic_harness.llm.provider import LLMProvider, ToolCallData, ToolCallResponse


# ── Mock LLM for deterministic agent-loop tests ──────────────────────

class _ToolLLM(LLMProvider):
    """LLM that returns a fixed sequence of tool call responses.

    Each call to *generate_with_tools* yields the next response in
    *responses*. When exhausted, returns *content* (default "done") with
    no tool calls.
    """

    def __init__(self, responses: list[ToolCallResponse]) -> None:
        self.responses = responses
        self.idx = 0

    async def generate(self, system: str, user: str, config=None):
        raise NotImplementedError

    async def generate_with_tools(self, messages, tools, config=None):
        if self.idx >= len(self.responses):
            return ToolCallResponse(content="done", model="mock")
        resp = self.responses[self.idx]
        self.idx += 1
        return resp

    async def generate_structured(self, system, user, response_model, config=None):
        raise NotImplementedError


def _make_agent(runtime: Runtime, description: str, **agent_kwargs: object) -> Agent:
    task = Task(description=description)
    task.status = TaskStatus.running
    agent = Agent("test-agent", task, runtime, **agent_kwargs)  # type: ignore[arg-type]
    runtime._agents[agent.id] = agent
    return agent


# ── ToolRegistry: token_limit / token_offset ──────────────────────────

def _make_registry() -> ToolRegistry:
    reg = ToolRegistry()
    from dynamic_harness.core.capabilities import _tool_read, _tool_grep, _tool_bash
    reg.register(
        ToolDef(name="read", description="Read a file", input_schema={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}),
        _tool_read,
    )
    reg.register(
        ToolDef(name="grep", description="Search files", input_schema={"type": "object", "properties": {"pattern": {"type": "string"}, "include": {"type": "string"}, "path": {"type": "string"}}, "required": ["pattern"]}),
        _tool_grep,
    )
    reg.register(
        ToolDef(name="bash", description="Run command", input_schema={"type": "object", "properties": {"command": {"type": "string"}, "timeout": {"type": "integer"}}, "required": ["command"]}),
        _tool_bash,
    )
    return reg


@pytest.mark.asyncio
async def test_token_limit_defaults_to_100_tokens(runtime: Runtime) -> None:
    reg = _make_registry()
    agent = _make_agent(runtime, "test")
    long_text = "hello world " * 500  # ~6000 chars
    f = runtime.generated_root / "long.txt"
    f.write_text(long_text)
    result = await reg.execute("read", "tc1", agent=agent, path=str(f))
    assert len(result.content) <= 100 * 4 + 200  # 100 tokens + truncation msg overhead
    assert "token_offset" in result.content  # hint for pagination


@pytest.mark.asyncio
async def test_token_limit_can_be_increased(runtime: Runtime) -> None:
    reg = _make_registry()
    agent = _make_agent(runtime, "test")
    f = runtime.generated_root / "data.txt"
    f.write_text("a" * 2000)
    result = await reg.execute("read", "tc1", agent=agent, path=str(f), token_limit=500)
    assert len(result.content) >= 500 * 4 - 100  # roughly 2000 chars
    assert "token_offset" not in result.content  # no truncation needed


@pytest.mark.asyncio
async def test_token_offset_skips_content(runtime: Runtime) -> None:
    reg = _make_registry()
    agent = _make_agent(runtime, "test")
    f = runtime.generated_root / "paged.txt"
    f.write_text("A" * 500 + "B" * 500)  # 1000 chars
    result_0 = await reg.execute("read", "tc1", agent=agent, path=str(f), token_limit=50, token_offset=0)
    result_1 = await reg.execute("read", "tc2", agent=agent, path=str(f), token_limit=50, token_offset=150)  # 150*4=600 chars into file = B region
    assert result_0.content != result_1.content
    assert result_0.content.startswith("A")
    assert result_1.content.startswith("B")


@pytest.mark.asyncio
async def test_token_offset_beyond_content_returns_short_message(runtime: Runtime) -> None:
    reg = _make_registry()
    agent = _make_agent(runtime, "test")
    f = runtime.generated_root / "short.txt"
    f.write_text("hi")
    result = await reg.execute("read", "tc1", agent=agent, path=str(f), token_limit=50, token_offset=1000)
    assert "offset beyond content" in result.content


@pytest.mark.asyncio
async def test_token_offset_zero_returns_start(runtime: Runtime) -> None:
    reg = _make_registry()
    agent = _make_agent(runtime, "test")
    f = runtime.generated_root / "start.txt"
    f.write_text("beginning" + "x" * 500)  # long enough to trigger truncation
    result = await reg.execute("read", "tc1", agent=agent, path=str(f), token_offset=0)
    assert result.content.startswith("beginning")
    assert "token_offset" in result.content  # truncated since default 100 tok


@pytest.mark.asyncio
async def test_token_limit_on_grep(runtime: Runtime) -> None:
    reg = _make_registry()
    agent = _make_agent(runtime, "test")
    for i in range(20):
        (runtime.generated_root / f"f{i}.txt").write_text(f"match line A\nmatch line B\nother\n")
    result = await reg.execute("grep", "tc1", agent=agent, pattern="match", path=str(runtime.generated_root), token_limit=10)
    assert len(result.content) <= 10 * 4 + 300
    assert "more)" in result.content or "(offset beyond" in result.content or "No matches" in result.content


@pytest.mark.asyncio
async def test_token_limit_on_bash(runtime: Runtime) -> None:
    reg = _make_registry()
    agent = _make_agent(runtime, "test")
    result = await reg.execute("bash", "tc1", agent=agent, command="echo hello && echo world && echo done", token_limit=2)
    assert "hello" in result.content
    assert len(result.content) <= 200


@pytest.mark.asyncio
async def test_token_offset_on_bash(runtime: Runtime) -> None:
    reg = _make_registry()
    agent = _make_agent(runtime, "test")
    result = await reg.execute("bash", "tc1", agent=agent, command="printf 'AAAA\\nBBBB\\nCCCC\\n'", token_limit=2, token_offset=0)
    first = result.content
    assert first.startswith("AA")
    result2 = await reg.execute("bash", "tc2", agent=agent, command="printf 'AAAA\\nBBBB\\nCCCC\\n'", token_limit=2, token_offset=1)
    second = result2.content
    assert first != second


# ── OpenAPI schemas includes token_limit / token_offset ──────────────

def test_openai_schemas_include_token_params(runtime: Runtime) -> None:
    schemas = runtime.tool_registry.openai_schemas()
    for s in schemas:
        props = s["function"]["parameters"].get("properties", {})
        assert "token_limit" in props, f"{s['function']['name']} missing token_limit"
        assert "token_offset" in props, f"{s['function']['name']} missing token_offset"
        assert props["token_limit"]["type"] == "integer"
        assert props["token_offset"]["type"] == "integer"


# ── Gitignore-based filtering in grep ────────────────────────────────
# Note: gitignore filter reads from Path.cwd() (project root .gitignore).
# Tests use the project's own .gitignore patterns.

@pytest.mark.asyncio
async def test_grep_skips_gitignored_directory(runtime: Runtime) -> None:
    """Verify grep respects project .gitignore (e.g. venv/ is ignored)."""
    agent = _make_agent(runtime, "test")
    proj = runtime.generated_root / "grep_gitignore_test"
    proj.mkdir()
    (proj / "visible.txt").write_text("needle")
    ignored = proj / "venv"
    ignored.mkdir()
    (ignored / "secret.txt").write_text("needle")
    result = await runtime.tool_registry.execute(
        "grep", "tc1", agent=agent, pattern="needle", path=str(proj),
    )
    assert "visible.txt" in result.content
    assert "secret.txt" not in result.content


@pytest.mark.asyncio
async def test_grep_all_in_ignored_dir_returns_no_matches(runtime: Runtime) -> None:
    """When all matching files live in a gitignored directory, show no matches."""
    agent = _make_agent(runtime, "test")
    proj = runtime.generated_root / "grep_all_ignored"
    proj.mkdir()
    ignored = proj / "venv"
    ignored.mkdir()
    (ignored / "data.txt").write_text("needle")
    result = await runtime.tool_registry.execute(
        "grep", "tc1", agent=agent, pattern="needle", path=str(proj),
    )
    assert result.content == "No matches found"


# ── Full agent loop with deterministic tool calls ────────────────────

@pytest.mark.asyncio
async def test_agent_reads_file_and_reports(runtime: Runtime) -> None:
    f = runtime.generated_root / "greeting.txt"
    f.write_text("Hello, Agent!")
    runtime.set_llm(_ToolLLM([
        ToolCallResponse(
            tool_calls=[ToolCallData(id="c1", name="read", arguments={"path": str(f)})],
            content=None, model="mock",
        ),
        ToolCallResponse(
            tool_calls=None,
            content="Read the file. Contents: Hello, Agent!",
            model="mock",
        ),
    ]))
    agent = _make_agent(runtime, "Read greeting.txt and report")
    await agent.run()
    assert agent.task.status.value == "completed"
    assert agent._last_report is not None
    assert "Hello" in agent._last_report.summary


@pytest.mark.asyncio
async def test_agent_write_then_read_then_report(runtime: Runtime) -> None:
    f = runtime.generated_root / "output.txt"
    runtime.set_llm(_ToolLLM([
        ToolCallResponse(
            tool_calls=[ToolCallData(id="c1", name="write", arguments={"path": str(f), "content": "data-123"})],
            content=None, model="mock",
        ),
        ToolCallResponse(
            tool_calls=[ToolCallData(id="c2", name="read", arguments={"path": str(f)})],
            content=None, model="mock",
        ),
        ToolCallResponse(
            tool_calls=None,
            content="Wrote data-123 and verified it.", model="mock",
        ),
    ]))
    agent = _make_agent(runtime, "Write data-123 to output.txt, verify, report")
    await agent.run()
    assert agent.task.status.value == "completed"
    assert "data-123" in f.read_text()
    assert "data-123" in agent._last_report.summary


@pytest.mark.asyncio
async def test_agent_delegates_and_reports(runtime: Runtime) -> None:
    runtime.set_llm(_ToolLLM([
        ToolCallResponse(
            tool_calls=[ToolCallData(id="c1", name="delegate", arguments={"description": "child task"})],
            content=None, model="mock",
        ),
        ToolCallResponse(
            tool_calls=None,
            content="Delegated successfully. Child completed.", model="mock",
        ),
    ]))
    agent = _make_agent(runtime, "Delegate a subtask and report")
    await agent.run()
    assert agent.task.status.value == "completed"
    assert agent._last_report is not None


@pytest.mark.asyncio
async def test_agent_continues_on_tool_error(runtime: Runtime) -> None:
    """Tool errors don't crash the agent; it logs the error and continues."""
    runtime.set_llm(_ToolLLM([
        ToolCallResponse(
            tool_calls=[ToolCallData(id="c1", name="read", arguments={"path": "/nonexistent.txt"})],
            content=None, model="mock",
        ),
        ToolCallResponse(
            tool_calls=None,
            content="The file doesn't exist, I'll report that.", model="mock",
        ),
    ]))
    agent = _make_agent(runtime, "Read a nonexistent file")
    await agent.run()
    assert agent.task.status.value == "completed"
    assert agent._last_report is not None
    assert "doesn't exist" in agent._last_report.summary or "The file" in agent._last_report.summary


@pytest.mark.asyncio
async def test_agent_glob_and_report(runtime: Runtime) -> None:
    (runtime.generated_root / "a.py").write_text("")
    (runtime.generated_root / "b.py").write_text("")
    runtime.set_llm(_ToolLLM([
        ToolCallResponse(
            tool_calls=[ToolCallData(id="c1", name="glob", arguments={"pattern": str(runtime.generated_root / "*.py")})],
            content=None, model="mock",
        ),
        ToolCallResponse(
            tool_calls=None,
            content="Found .py files.", model="mock",
        ),
    ]))
    agent = _make_agent(runtime, "Find .py files and report")
    await agent.run()
    assert agent.task.status.value == "completed"


@pytest.mark.asyncio
async def test_agent_repeated_tool_calls_triggers_safety(runtime: Runtime) -> None:
    """Safety: repeated identical tool calls should force-fail."""
    runtime.set_llm(_ToolLLM([
        ToolCallResponse(
            tool_calls=[ToolCallData(id="c1", name="read", arguments={"path": "/x.txt"})],
            content=None, model="mock",
        ),
        ToolCallResponse(
            tool_calls=[ToolCallData(id="c2", name="read", arguments={"path": "/x.txt"})],
            content=None, model="mock",
        ),
        ToolCallResponse(
            tool_calls=[ToolCallData(id="c3", name="read", arguments={"path": "/x.txt"})],
            content=None, model="mock",
        ),
        ToolCallResponse(
            tool_calls=[ToolCallData(id="c4", name="read", arguments={"path": "/x.txt"})],
            content=None, model="mock",
        ),
        ToolCallResponse(
            tool_calls=[ToolCallData(id="c5", name="read", arguments={"path": "/x.txt"})],
            content=None, model="mock",
        ),
    ]))
    agent = _make_agent(runtime, "Repeated read calls", repeated_call_limit=3)
    await agent.run()
    assert agent.task.status.value == "failed"


@pytest.mark.asyncio
async def test_agent_varied_tool_calls_do_not_trigger_safety(runtime: Runtime) -> None:
    (runtime.generated_root / "a.txt").write_text("a")
    (runtime.generated_root / "b.txt").write_text("b")
    runtime.set_llm(_ToolLLM([
        ToolCallResponse(
            tool_calls=[ToolCallData(id="c1", name="read", arguments={"path": str(runtime.generated_root / "a.txt")})],
            content=None, model="mock",
        ),
        ToolCallResponse(
            tool_calls=[ToolCallData(id="c2", name="read", arguments={"path": str(runtime.generated_root / "b.txt")})],
            content=None, model="mock",
        ),
        ToolCallResponse(
            tool_calls=None,
            content="Read both files.", model="mock",
        ),
    ]))
    agent = _make_agent(runtime, "Read two different files", repeated_call_limit=3)
    await agent.run()
    assert agent.task.status.value == "completed"


@pytest.mark.asyncio
async def test_agent_pages_through_file_with_token_offset(runtime: Runtime) -> None:
    """Agent reads a large file in chunks using token_limit/token_offset.

    The file is too large to fit in a single default read (100 tokens ≈ 400
    chars). The agent reads the first chunk, sees the truncation hint, then
    requests subsequent chunks via token_offset, and finally reports with
    the combined content.
    """
    f = runtime.generated_root / "large.txt"
    # Build a file with numbered sections; each section is ~150 chars
    lines = [f"Section {i:03d}: " + "x" * 140 + "\n" for i in range(20)]
    f.write_text("".join(lines))  # ~3000 chars total

    # Each read uses token_limit=50 (200 chars) so roughly 1-2 sections per read.
    # Offset = 0 → chars 0-199 = sections 0-1
    # Offset = 50 → chars 200-399 = sections 1-3
    # Offset = 100 → chars 400-599 = sections 2-4
    runtime.set_llm(_ToolLLM([
        # Read first chunk
        ToolCallResponse(
            tool_calls=[ToolCallData(id="c1", name="read", arguments={
                "path": str(f), "token_limit": 50, "token_offset": 0,
            })],
            content=None, model="mock",
        ),
        # Read second chunk
        ToolCallResponse(
            tool_calls=[ToolCallData(id="c2", name="read", arguments={
                "path": str(f), "token_limit": 50, "token_offset": 50,
            })],
            content=None, model="mock",
        ),
        # Report after reading first two chunks
        ToolCallResponse(
            tool_calls=None,
            content="Combined: Section 000 and Section 001 and Section 002.",
            model="mock",
        ),
    ]))
    agent = _make_agent(runtime, "Read large.txt in chunks and report")
    await agent.run()
    assert agent.task.status.value == "completed"
    assert "Section 000" in agent._last_report.summary
    assert "Section 001" in agent._last_report.summary
    assert "Section 002" in agent._last_report.summary


@pytest.mark.asyncio
async def test_agent_reasoning_through_paginated_data(runtime: Runtime) -> None:
    """Agent reads incremental data across calls, building understanding.

    The file starts with clues and later sections have the answer.
    The agent must read multiple pages to find the full answer.
    """
    f = runtime.generated_root / "treasure.txt"
    parts = [
        "The treasure is buried under the big tree.\n",
        "The big tree is next to the old well.\n",
        "The old well is behind the red barn.\n",
        "THE TREASURE: a chest of gold coins.\n",
        "Map reference: grid B-7, depth 3ft.\n",
    ]
    f.write_text("".join(parts))  # ~250 chars total

    # Agent reads the first 100 chars, sees hint about more content,
    # then reads next chunk with offset, finds the treasure
    runtime.set_llm(_ToolLLM([
        # First read: gets first ~100 chars (tree + well)
        ToolCallResponse(
            tool_calls=[ToolCallData(id="c1", name="read", arguments={
                "path": str(f), "token_limit": 25, "token_offset": 0,
            })],
            content=None, model="mock",
        ),
        # Second read: gets chars 100-199 (barn + treasure)
        ToolCallResponse(
            tool_calls=[ToolCallData(id="c2", name="read", arguments={
                "path": str(f), "token_limit": 25, "token_offset": 25,
            })],
            content=None, model="mock",
        ),
        # Read final chunk to get map reference
        ToolCallResponse(
            tool_calls=[ToolCallData(id="c3", name="read", arguments={
                "path": str(f), "token_limit": 25, "token_offset": 50,
            })],
            content=None, model="mock",
        ),
        # All data collected, report
        ToolCallResponse(
            tool_calls=None,
            content="Found treasure at grid B-7, depth 3ft.",
            model="mock",
        ),
    ]))
    agent = _make_agent(runtime, "Read treasure.txt page by page and report the treasure location")
    await agent.run()
    assert agent.task.status.value == "completed"
    assert "B-7" in agent._last_report.summary


# ── Compress tool ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_compress_tool_with_messages(runtime: Runtime) -> None:
    agent = _make_agent(runtime, "test")
    agent._messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "user"},
        {"role": "assistant", "content": "assistant"},
    ]
    result = await runtime.tool_registry.execute("compress", "tc1", agent=agent)
    assert "No LLM available" in result.content


# ── Converse tool (covered by existing tests in test_capabilities.py) ──

@pytest.mark.asyncio
async def test_converse_tool_nonexistent_agent(runtime: Runtime) -> None:
    agent = _make_agent(runtime, "parent")
    result = await runtime.tool_registry.execute("converse", "tc1", agent=agent, agent_id="nonexistent", message="hello")
    assert "no agent found" in result.content


# ── Escalate ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_escalate_tool_via_agent_test(agent_test: AgentTest) -> None:
    class EscalatingAgent(Agent):
        async def run(self) -> None:
            self.escalate("I need help with this task")

    agent_test.runtime.register_agent_class("EscalatingAgent", EscalatingAgent)
    await agent_test.run("Escalate task", agent_type="EscalatingAgent")
    assert agent_test.status == "escalated"


# ── AgentTest helper ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_agent_test_helper_fails_without_llm(agent_test: AgentTest) -> None:
    await agent_test.run("Some task")
    assert agent_test.status == "failed"
    assert agent_test.failure


@pytest.mark.asyncio
async def test_agent_test_helper_completes_with_llm(runtime: Runtime, agent_test: AgentTest) -> None:
    runtime.set_llm(_ToolLLM([
        ToolCallResponse(
            tool_calls=None,
            content="Task complete.", model="mock",
        ),
    ]))
    await agent_test.run("Do something")
    assert agent_test.status == "completed"
    assert "Task complete" in agent_test.summary