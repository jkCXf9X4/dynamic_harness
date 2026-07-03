from __future__ import annotations

import json as _json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from pydantic import BaseModel

if TYPE_CHECKING:
    from .agent import Agent


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

TOOL_SPAWN_DEF = ToolDef(
    name="spawn",
    description="Spawn a sub-agent to handle a subtask, then return its results",
    input_schema={
        "type": "object",
        "properties": {
            "description": {"type": "string", "description": "Description of subtask for the sub-agent"},
        },
        "required": ["description"],
    },
)

TOOL_REPORT_DEF = ToolDef(
    name="report",
    description="Report final results to parent agent and complete this agent's work",
    input_schema={
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "Summary of findings"},
            "artifact_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Artifact IDs to attach",
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


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

async def _tool_read(*, agent: Agent, path: str) -> str:
    return Path(path).read_text()


async def _tool_write(*, agent: Agent, path: str, content: str) -> str:
    Path(path).write_text(content)
    return f"Wrote {len(content)} bytes to {path}"


async def _tool_glob(*, agent: Agent, pattern: str) -> str:
    import glob as _glob
    matches = _glob.glob(pattern, recursive=True)
    return _json.dumps(sorted(matches), indent=2)


async def _tool_webfetch(*, agent: Agent, url: str) -> str:
    import httpx as _httpx
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


async def _tool_spawn(*, agent: Agent, description: str) -> str:
    child = agent.spawn(description)
    await child.run()
    return f"Spawned agent completed. Status: {child.task.status.value}. ID: {child.id}"


async def _tool_report(*, agent: Agent, summary: str, artifact_ids: list[str] | None = None) -> str:
    from .task import ReportPayload
    agent.report(ReportPayload(
        task_id=agent.task.id,
        summary=summary,
        artifact_ids=artifact_ids or [],
    ))
    return f"Reported: {summary[:100]}"


async def _tool_escalate(*, agent: Agent, issue: str) -> str:
    agent.escalate(issue)
    return f"Escalated: {issue[:100]}"


async def _tool_fail(*, agent: Agent, error: str) -> str:
    agent.fail(error)
    return f"Failed: {error[:100]}"


def register_default_tools(registry: ToolRegistry) -> None:
    registry.register(TOOL_READ_DEF, _tool_read)
    registry.register(TOOL_WRITE_DEF, _tool_write)
    registry.register(TOOL_GLOB_DEF, _tool_glob)
    registry.register(TOOL_WEBFETCH_DEF, _tool_webfetch)
    registry.register(TOOL_EDIT_DEF, _tool_edit)
    registry.register(TOOL_SPAWN_DEF, _tool_spawn)
    registry.register(TOOL_REPORT_DEF, _tool_report)
    registry.register(TOOL_ESCALATE_DEF, _tool_escalate)
    registry.register(TOOL_FAIL_DEF, _tool_fail)
