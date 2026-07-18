from __future__ import annotations

import asyncio
import glob as _glob
import json as _json
import re as _re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable

import httpx as _httpx
from pydantic import BaseModel

if TYPE_CHECKING:
    from .agent import Agent

from .task import Failure, ReportPayload, TaskStatus, ActivityEvent, ActivityEventType


ToolFunc = Callable[..., Awaitable[str]]


class ToolDef(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any]


class ToolResult:
    def __init__(self, tool_call_id: str, content: str) -> None:
        self.tool_call_id = tool_call_id
        self.content = content


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, tuple[ToolDef, ToolFunc]] = {}

    def register(self, tool_def: ToolDef, fn: ToolFunc) -> None:
        self._tools[tool_def.name] = (tool_def, fn)

    def get(self, name: str) -> tuple[ToolDef, ToolFunc] | None:
        return self._tools.get(name)

    async def execute(self, name: str, tool_call_id: str, agent: Agent, **kwargs: Any) -> ToolResult:
        entry = self._tools.get(name)
        if not entry:
            return ToolResult(tool_call_id=tool_call_id, content=f"Error: unknown tool '{name}'")
        _, fn = entry
        try:
            content = await fn(agent=agent, **kwargs)
            return ToolResult(tool_call_id=tool_call_id, content=content)
        except Exception as e:
            return ToolResult(tool_call_id=tool_call_id, content=f"Error executing {name}: {e}")

    def openai_schemas(self) -> list[dict]:
        result: list[dict] = []
        for td, _ in self._tools.values():
            result.append({
                "type": "function",
                "function": {
                    "name": td.name,
                    "description": td.description,
                    "parameters": td.input_schema,
                },
            })
        return result

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())


TOOL_READ_DEF = ToolDef(
    name="read",
    description="Read a file from disk by path",
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute or relative file path"},
        },
        "required": ["path"],
    },
)

TOOL_WRITE_DEF = ToolDef(
    name="write",
    description="Write content to a file on disk",
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute or relative file path"},
            "content": {"type": "string", "description": "Content to write"},
        },
        "required": ["path", "content"],
    },
)

TOOL_GLOB_DEF = ToolDef(
    name="glob",
    description="List files matching a glob pattern",
    input_schema={
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Glob pattern (e.g. **/*.py)"},
        },
        "required": ["pattern"],
    },
)

TOOL_WEBFETCH_DEF = ToolDef(
    name="webfetch",
    description="Fetch content from a URL",
    input_schema={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Fully qualified URL to fetch"},
        },
        "required": ["url"],
    },
)

TOOL_EDIT_DEF = ToolDef(
    name="edit",
    description="Replace old_string with new_string in a file",
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to edit"},
            "old_string": {"type": "string", "description": "Text to find and replace"},
            "new_string": {"type": "string", "description": "Replacement text"},
        },
        "required": ["path", "old_string", "new_string"],
    },
)

TOOL_DELEGATE_DEF = ToolDef(
    name="delegate",
    description="Delegate a task to a sub-agent that handles it autonomously. "
                "The sub-agent sees ONLY your description, role, and optional "
                "system_prompt — nothing from your parent. "
                "Use system_prompt to override the sub-agent's default behavior. "
                "Returns the child's status, ID, report summary, "
                "artifact IDs, and confidence (if set). For failed children, "
                "returns the failure reason.",
    input_schema={
        "type": "object",
        "properties": {
            "description": {"type": "string", "description": "Description of the task for the sub-agent"},
            "role": {"type": "string", "description": "Optional role tag scoping the sub-agent's focus (e.g. 'You are a Security Auditor. Flag issues, do not fix them.')"},
            "system_prompt": {"type": "string", "description": "Optional custom system prompt for the sub-agent. Overrides the default agent behavior. Use for A/B testing different prompt strategies."},
        },
        "required": ["description"],
    },
)

TOOL_REPORT_DEF = ToolDef(
    name="report",
    description="Report final results to parent agent and complete this agent's work. "
                "Include a concrete summary of findings, artifact_ids referencing any "
                "files written, optionally a technical analysis and full report, and "
                "optionally a confidence score (0.0–1.0).",
    input_schema={
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "Summary of findings"},
            "artifact_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Artifact IDs to attach",
            },
            "technical_summary": {
                "type": "string",
                "description": "Optional detailed technical analysis of findings",
            },
            "full_report": {
                "type": "string",
                "description": "Optional complete report with full detail",
            },
            "confidence": {
                "type": "number",
                "description": "Optional confidence score (0.0 = uncertain, 1.0 = certain)",
            },
        },
        "required": ["summary"],
    },
)

TOOL_ESCALATE_DEF = ToolDef(
    name="escalate",
    description="Escalate an issue to the parent agent",
    input_schema={
        "type": "object",
        "properties": {
            "issue": {"type": "string", "description": "Description of the issue"},
        },
        "required": ["issue"],
    },
)

TOOL_FAIL_DEF = ToolDef(
    name="fail",
    description="Report a failure and terminate this agent's work",
    input_schema={
        "type": "object",
        "properties": {
            "error": {"type": "string", "description": "Error message"},
        },
        "required": ["error"],
    },
)

TOOL_GREP_DEF = ToolDef(
    name="grep",
    description="Search file contents using a regular expression pattern. Returns matching file paths and line numbers.",
    input_schema={
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Regex pattern to search for"},
            "include": {"type": "string", "description": "Glob pattern to filter files (e.g. *.py)"},
            "path": {"type": "string", "description": "Directory to search in (default: current)"},
        },
        "required": ["pattern"],
    },
)

TOOL_BASH_DEF = ToolDef(
    name="bash",
    description="Execute a shell command and return its output. Use for building, running tests, git operations, or any CLI task.",
    input_schema={
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute"},
            "timeout": {"type": "integer", "description": "Timeout in milliseconds (default 30000)"},
        },
        "required": ["command"],
    },
)

TOOL_ASK_DEF = ToolDef(
    name="ask",
    description="Ask the user a question and get their response. Use when you need input, clarification, or confirmation.",
    input_schema={
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "The question to present to the user"},
        },
        "required": ["question"],
    },
)

TOOL_COMPRESS_DEF = ToolDef(
    name="compress",
    description="Compress this agent's conversation context by asking the LLM "
                "to summarize all prior messages. The full history is replaced "
                "by a single compressed summary, reducing token usage and "
                "preventing context rot.",
    input_schema={
        "type": "object",
        "properties": {},
        "required": [],
    },
)

TOOL_CONVERSE_DEF = ToolDef(
    name="converse",
    description="Send a message to another agent (by ID) and wait for its "
                "response. The target agent resumes with this new message "
                "appended to its existing context. Use this to continue a "
                "conversation with a child agent after it has reported, or "
                "to request follow-up work from a completed child agent.",
    input_schema={
        "type": "object",
        "properties": {
            "agent_id": {"type": "string", "description": "ID of the target agent (e.g. a child)"},
            "message": {"type": "string", "description": "Message or instruction for the target agent"},
        },
        "required": ["agent_id", "message"],
    },
)

TOOL_READ_ARTIFACT_DEF = ToolDef(
    name="read_artifact",
    description="Read an artifact by its ID. Artifacts are stored when agents call "
                "report(). Use this to look up a child agent's report contents by its "
                "artifact ID. Returns the artifact's headline and summary views.",
    input_schema={
        "type": "object",
        "properties": {
            "artifact_id": {"type": "string", "description": "The ID of the artifact to read"},
        },
        "required": ["artifact_id"],
    },
)


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

async def _tool_read(*, agent: Agent, path: str) -> str:
    return Path(path).read_text()


async def _tool_write(*, agent: Agent, path: str, content: str) -> str:
    Path(path).write_text(content)
    return f"Wrote {len(content)} bytes to {path}"


def _is_hidden(path: str | Path) -> bool:
    p = Path(path)
    for part in p.parts:
        if part.startswith("."):
            return True
    return False


def _build_gitignore_filter() -> Callable[[str], bool]:
    gitignore = Path.cwd() / ".gitignore"
    if not gitignore.exists():
        return lambda p: False

    try:
        import pathspec
        spec = pathspec.PathSpec.from_lines(
            "gitignore", gitignore.read_text().splitlines()
        )

        def is_ignored(path: str) -> bool:
            return spec.match_file(path)
    except ImportError:
        return lambda p: False

    return is_ignored


async def _tool_glob(*, agent: Agent, pattern: str) -> str:
    matches = _glob.glob(pattern, recursive=True)
    _filter = _build_gitignore_filter()
    filtered = [m for m in matches if not _filter(m) and not _is_hidden(m)]
    if filtered:
        return _json.dumps(sorted(filtered), indent=2)
    visible = [m for m in matches if not _is_hidden(m)]
    return _json.dumps(sorted(visible), indent=2)


async def _tool_webfetch(*, agent: Agent, url: str) -> str:
    async with _httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=30)
        resp.raise_for_status()
        return resp.text


async def _tool_edit(*, agent: Agent, path: str, old_string: str, new_string: str) -> str:
    content = Path(path).read_text()
    if old_string not in content:
        return f"Error: old_string not found in {path}"
    new_content = content.replace(old_string, new_string, 1)
    Path(path).write_text(new_content)
    return f"Replaced in {path}"


async def _tool_delegate(*, agent: Agent, description: str, role: str | None = None, system_prompt: str | None = None) -> str:
    child = agent.delegate(description, role=role, system_prompt=system_prompt)
    agent._runtime.emit_activity(ActivityEvent(
        agent_id=agent.id,
        event_type=ActivityEventType.DELEGATION_START,
        data={
            "child_id": child.id,
            "description": description[:200],
            "role": role,
        },
    ))
    await child.run()

    status = child.task.status.value
    agent._runtime.emit_activity(ActivityEvent(
        agent_id=agent.id,
        event_type=ActivityEventType.DELEGATION_END,
        data={
            "child_id": child.id,
            "status": status,
        },
    ))
    lines = [f"Delegated to agent {child.id}. Status: {status}"]

    if child._last_report:
        r = child._last_report
        lines.append(f"Summary: {r.summary[:500]}")
        if r.artifact_ids:
            lines.append(f"Artifact IDs: {', '.join(r.artifact_ids)}")
        if r.confidence is not None:
            lines.append(f"Confidence: {r.confidence:.2f}")

    if child._last_failure:
        lines.append(f"Failure: {child._last_failure.error[:500]}")

    return "\n".join(lines)


async def _tool_report(*, agent: Agent, summary: str, artifact_ids: list[str] | None = None, confidence: float | None = None, technical_summary: str | None = None, full_report: str | None = None) -> str:
    agent.report(ReportPayload(
        task_id=agent.task.id,
        summary=summary,
        artifact_ids=artifact_ids or [],
        confidence=confidence,
        technical_summary=technical_summary,
        full_report=full_report,
    ))
    return f"Reported: {summary[:100]}"


async def _tool_read_artifact(*, agent: Agent, artifact_id: str) -> str:
    artifact = agent._runtime.artifact_store.get(artifact_id)
    if not artifact:
        return f"Error: no artifact found with ID '{artifact_id}'"
    views = artifact.views
    parts = []
    for name in ("headline", "summary_200", "summary_1000", "technical", "full_report", "raw_data"):
        v = getattr(views, name, None)
        if v:
            parts.append(f"[{name}] {v}")
    return "\n".join(parts) if parts else f"Artifact {artifact_id} has no content."


async def _tool_escalate(*, agent: Agent, issue: str) -> str:
    agent.escalate(issue)
    return f"Escalated: {issue[:100]}"


async def _tool_fail(*, agent: Agent, error: str) -> str:
    agent.fail(error)
    return f"Failed: {error[:100]}"


async def _tool_ask(*, agent: Agent, question: str) -> str:
    loop = asyncio.get_event_loop()
    answer = await loop.run_in_executor(None, lambda: input(f"\n[Agent asks] {question}\nYour response: "))
    return answer.strip()


async def _tool_grep(*, agent: Agent, pattern: str, include: str | None = None, path: str | None = None) -> str:
    search_path = Path(path or ".")
    if not search_path.is_dir():
        return f"Error: {search_path} is not a directory"
    matches: list[str] = []
    for f in search_path.rglob(include or "*"):
        if not f.is_file():
            continue
        if _is_hidden(f):
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
            for i, line in enumerate(text.splitlines(), 1):
                if _re.search(pattern, line):
                    matches.append(f"{f}:{i}: {line.rstrip()[:200]}")
        except Exception:
            pass
    if not matches:
        return "No matches found"
    return _json.dumps(matches[:200], indent=2) + (f"\n... ({len(matches) - 200} more)" if len(matches) > 200 else "")


async def _tool_bash(*, agent: Agent, command: str, timeout: int = 30000) -> str:
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout / 1000)
    except TimeoutError:
        proc.kill()
        return f"Error: command timed out after {timeout}ms"
    result = ""
    if stdout:
        result += stdout.decode(errors="replace")
    if stderr:
        result += f"\n(STDERR)\n{stderr.decode(errors='replace')}"
    return result.strip() or "(no output)"


COMPRESSION_PROMPT = """\
You are a context compression engine. Condense the following agent
conversation into a single concise paragraph. Preserve:
- The original task and goals
- Key findings, decisions, and code changes
- Open questions and unresolved issues
- Current state and next steps

Output ONLY the summary paragraph, no preamble."""


async def _tool_compress(*, agent: Agent) -> str:
    if not agent._messages or len(agent._messages) < 3:
        return "Nothing to compress."
    llm = agent._runtime._llm
    if not llm:
        return "No LLM available for compression."

    compression_input = [
        {"role": "system", "content": COMPRESSION_PROMPT},
    ] + agent._messages[1:]

    response = await llm.generate_with_tools(compression_input, tools=[])
    summary = (response.content or "").strip()
    if not summary:
        return "Compression produced empty summary."

    before = len(agent._messages)
    agent._messages = [
        agent._messages[0],
        {"role": "system", "content": f"[Context compressed] {summary}"},
    ]
    after = len(agent._messages)
    saved = before - after
    agent._runtime.emit_activity(ActivityEvent(
        agent_id=agent.id,
        event_type=ActivityEventType.COMPRESSION,
        data={
            "before": before,
            "after": after,
            "saved": saved,
        },
    ))
    return f"Compressed: {before} messages -> {after} messages ({saved} removed).\nSummary: {summary[:200]}..."


async def _tool_converse(*, agent: Agent, agent_id: str, message: str) -> str:
    target = agent._runtime._agents.get(agent_id)
    if not target:
        return f"Error: no agent found with ID {agent_id}"
    if target.task.status not in (TaskStatus.completed, TaskStatus.running):
        return f"Error: agent {agent_id} status is '{target.task.status.value}', cannot converse"

    await target.continue_with_input(message)

    summary = ""
    for msg in reversed(target._messages or []):
        if msg.get("role") == "assistant" and msg.get("content"):
            summary = msg["content"][:500]
            break
    status = target.task.status.value
    return f"[Agent {agent_id[:8]}] {summary}\n(Status: {status})"


def register_default_tools(registry: ToolRegistry) -> None:
    registry.register(TOOL_READ_DEF, _tool_read)
    registry.register(TOOL_WRITE_DEF, _tool_write)
    registry.register(TOOL_GLOB_DEF, _tool_glob)
    registry.register(TOOL_GREP_DEF, _tool_grep)
    registry.register(TOOL_BASH_DEF, _tool_bash)
    registry.register(TOOL_WEBFETCH_DEF, _tool_webfetch)
    registry.register(TOOL_EDIT_DEF, _tool_edit)
    registry.register(TOOL_DELEGATE_DEF, _tool_delegate)
    registry.register(TOOL_REPORT_DEF, _tool_report)
    registry.register(TOOL_ESCALATE_DEF, _tool_escalate)
    registry.register(TOOL_FAIL_DEF, _tool_fail)
    registry.register(TOOL_ASK_DEF, _tool_ask)
    registry.register(TOOL_COMPRESS_DEF, _tool_compress)
    registry.register(TOOL_CONVERSE_DEF, _tool_converse)
    registry.register(TOOL_READ_ARTIFACT_DEF, _tool_read_artifact)
