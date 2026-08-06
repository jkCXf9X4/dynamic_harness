from __future__ import annotations

import asyncio
import glob as _glob
import ipaddress as _ipaddress
import json as _json
import re as _re
import shlex as _shlex
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable
from urllib.parse import urlparse as _urlparse

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
        token_limit: int = kwargs.pop("token_limit", 100)
        token_offset: int = kwargs.pop("token_offset", 0)
        entry = self._tools.get(name)
        if not entry:
            return ToolResult(tool_call_id=tool_call_id, content=f"Error: unknown tool '{name}'")
        _, fn = entry
        try:
            content = await fn(agent=agent, **kwargs)
        except Exception as e:
            return ToolResult(tool_call_id=tool_call_id, content=f"Error executing {name}: {e}")

        char_limit = max(1, token_limit * 4)
        char_offset = max(0, token_offset * 4)
        total_chars = len(content)
        if char_offset >= total_chars:
            return ToolResult(tool_call_id=tool_call_id, content="(offset beyond content length)")
        content = content[char_offset:]
        if len(content) > char_limit:
            content = content[:char_limit] + (
                f"\n... ({token_limit} tokens shown, {total_chars // 4} total. "
                f"Use token_offset={token_offset + token_limit} to see more)"
            )
        return ToolResult(tool_call_id=tool_call_id, content=content)

    def openai_schemas(self) -> list[dict]:
        result: list[dict] = []
        for td, _ in self._tools.values():
            schema = dict(td.input_schema)
            schema["properties"] = dict(schema.get("properties", {}))
            schema["properties"]["token_limit"] = {
                "type": "integer",
                "description": "Max tokens to return (1 token ≈ 4 chars). Default 100.",
            }
            schema["properties"]["token_offset"] = {
                "type": "integer",
                "description": "Skip this many tokens from the start. Default 0.",
            }
            result.append({
                "type": "function",
                "function": {
                    "name": td.name,
                    "description": td.description,
                    "parameters": schema,
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
    description="Replace the first occurrence of old_string with new_string in a file. "
                "Only the first match is replaced. Provide enough surrounding context "
                "in old_string to uniquely identify the target location.",
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
    description="Execute a command and return its output. The command is split into arguments "
                "by shell quoting rules — no shell operators (pipes, redirects, &&, ||, etc.) "
                "are supported. Use for building, running tests, git operations, or any CLI task.",
    input_schema={
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Command with arguments to execute (shell operators like | > && are NOT supported)"},
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

TOOL_PRUNE_DEF = ToolDef(
    name="prune",
    description="Remove stale or irrelevant committed turns from this agent's "
                "context to reduce token usage. Turns are identified by the "
                "prune_id shown in the Context Observation (e.g. 't3'). A turn "
                "is the assistant message plus its tool results — all are "
                "removed together and replaced by a short PRUNED marker. The "
                "full content is kept in memory and can be retrieved later via "
                "restore(prune_id=...). The task definition and system prompt "
                "are never touched. Prefer this over compress() when only a "
                "few turns are stale.",
    input_schema={
        "type": "object",
        "properties": {
            "prune_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Turn ids (from Context Observation 'prune_id:tools') to prune",
            },
        },
        "required": ["prune_ids"],
    },
)

TOOL_RESTORE_DEF = ToolDef(
    name="restore",
    description="Bring a previously pruned turn (assistant message + its tool "
                "results) back into this agent's context. The turn is "
                "re-inserted at the location of its PRUNED marker. Use this "
                "when a dropped tool result turns out to be needed after all.",
    input_schema={
        "type": "object",
        "properties": {
            "prune_id": {"type": "string", "description": "Turn id to restore, e.g. 't3'"},
        },
        "required": ["prune_id"],
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

def _resolve_safe_path(path: str, agent: Agent) -> Path:
    sandbox = agent.generated_root or Path.cwd()
    p = Path(path)
    if p.is_absolute():
        resolved = p.resolve()
    else:
        resolved = (sandbox / p).resolve()
    if sandbox not in resolved.parents and resolved != sandbox:
        raise ValueError(f"Path '{path}' is outside the workspace")
    return resolved


async def _tool_read(*, agent: Agent, path: str) -> str:
    try:
        safe = _resolve_safe_path(path, agent)
    except ValueError as e:
        return f"Error: {e}"
    return safe.read_text()


async def _tool_write(*, agent: Agent, path: str, content: str) -> str:
    try:
        safe = _resolve_safe_path(path, agent)
    except ValueError as e:
        return f"Error: {e}"
    safe.parent.mkdir(parents=True, exist_ok=True)
    previous = safe.read_text() if safe.exists() else None
    safe.write_text(content)
    if previous == content:
        return (
            f"No change: content identical to existing file at {path} — "
            f"the file already contains exactly this. Produce NEW content "
            f"or move on; do not re-write the same content."
        )
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
    _filter = agent.get_gitignore_filter()
    filtered = [m for m in matches if not _filter(m) and not _is_hidden(m)]
    if filtered:
        return _json.dumps(sorted(filtered), indent=2)
    visible = [m for m in matches if not _is_hidden(m)]
    return _json.dumps(sorted(visible), indent=2)


async def _tool_webfetch(*, agent: Agent, url: str) -> str:
    try:
        parsed = _urlparse(url)
    except Exception:
        return f"Error: invalid URL '{url}'"

    if parsed.scheme not in ("http", "https"):
        return f"Error: unsupported URL scheme '{parsed.scheme}'. Only http and https are allowed."

    hostname = parsed.hostname
    if not hostname:
        return f"Error: no hostname in URL '{url}'"

    try:
        addr = _ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        if addr.is_loopback or addr.is_private or addr.is_link_local or addr.is_multicast:
            return f"Error: URL resolves to a restricted address ({hostname})."

    async with _httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=30)
        resp.raise_for_status()
        return resp.text


async def _tool_edit(*, agent: Agent, path: str, old_string: str, new_string: str) -> str:
    try:
        safe = _resolve_safe_path(path, agent)
    except ValueError as e:
        return f"Error: {e}"
    content = safe.read_text()
    if old_string not in content:
        return f"Error: old_string not found in {path}"
    new_content = content.replace(old_string, new_string, 1)
    safe.write_text(new_content)
    return f"Replaced in {path}"


def _format_delegate_result(child: Agent) -> str:
    status = child.task.status.value
    child._runtime.emit_activity(ActivityEvent(
        agent_id=child.parent.id if child.parent else "",
        event_type=ActivityEventType.DELEGATION_END,
        data={
            "child_id": child.id,
            "status": status,
        },
    ))
    result: dict[str, Any] = {
        "child_id": child.id,
        "status": status,
    }

    if child._last_report:
        r = child._last_report
        result["summary"] = r.summary[:500]
        if r.artifact_ids:
            result["artifact_ids"] = r.artifact_ids
        if r.confidence is not None:
            result["confidence"] = r.confidence

    if child._last_failure:
        result["failure"] = child._last_failure.error[:500]

    return _json.dumps(result, indent=2)


async def _tool_delegate(
    *, agent: Agent, description: str,
    role: str | None = None, system_prompt: str | None = None,
    _tool_call_id: str = "",
) -> str:
    child = agent.delegate(description, role=role, system_prompt=system_prompt)
    agent.emit_activity(ActivityEvent(
        agent_id=agent.id,
        event_type=ActivityEventType.DELEGATION_START,
        data={
            "child_id": child.id,
            "description": description[:200],
            "role": role,
        },
    ))
    task = asyncio.create_task(child.run())
    if agent._deferred_delegates is not None:
        agent._deferred_delegates.append((_tool_call_id, child, task))
        return _json.dumps({"child_id": child.id, "status": "pending"}, indent=2)

    agent._pending_child_task = task
    try:
        await agent._pending_child_task
    except asyncio.CancelledError:
        agent._pending_child_task.cancel()
        try:
            await agent._pending_child_task
        except asyncio.CancelledError:
            pass
        raise
    finally:
        agent._pending_child_task = None

    return _format_delegate_result(child)


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
    artifact = agent._artifact_store.get(artifact_id)
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
    _filter = agent.get_gitignore_filter()
    matches: list[str] = []
    errors: int = 0
    for f in search_path.rglob(include or "*"):
        if not f.is_file():
            continue
        if _is_hidden(f):
            continue
        if _filter(str(f)):
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
            for i, line in enumerate(text.splitlines(), 1):
                if _re.search(pattern, line):
                    matches.append(f"{f}:{i}: {line.rstrip()[:200]}")
        except Exception:
            errors += 1
    result_parts: list[str] = []
    if not matches:
        result_parts.append("No matches found")
    else:
        result_parts.append(_json.dumps(matches[:200], indent=2))
        if len(matches) > 200:
            result_parts.append(f"... ({len(matches) - 200} more)")
    if errors:
        result_parts.append(f"({errors} file(s) could not be read)")
    return "\n".join(result_parts)


async def _tool_bash(*, agent: Agent, command: str, timeout: int = 30000) -> str:
    try:
        args = _shlex.split(command)
    except ValueError as e:
        return f"Error: invalid command syntax: {e}"

    cwd = agent.generated_root

    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout / 1000)
    except TimeoutError:
        proc.kill()
        try:
            await proc.wait()
        except Exception:
            pass
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
    llm = agent.llm
    if not llm:
        return "No LLM available for compression."

    compression_input = [
        {"role": "system", "content": COMPRESSION_PROMPT},
    ] + agent._messages[1:]

    response = None
    last_error = None
    for attempt in range(2):
        try:
            response = await llm.generate_with_tools(compression_input, tools=[])
            break
        except Exception as e:
            last_error = e
            if attempt == 0:
                continue

    if response is None:
        return f"Compression failed after 2 attempts: {last_error}"

    summary = (response.content or "").strip()
    if not summary:
        return "Compression produced empty summary."

    before = len(agent._messages)
    agent._messages = [
        agent._messages[0],
        {"role": "system", "content": f"[Context compressed] {summary}"},
    ]
    agent._pruned.clear()
    agent._prune_markers.clear()
    agent._turn_order.clear()
    agent._turns.clear()
    after = len(agent._messages)
    saved = before - after
    agent.emit_activity(ActivityEvent(
        agent_id=agent.id,
        event_type=ActivityEventType.COMPRESSION,
        data={
            "before": before,
            "after": after,
            "saved": saved,
        },
    ))
    return f"Compressed: {before} messages -> {after} messages ({saved} removed).\nSummary: {summary[:200]}..."


def _make_prune_marker(pid: str, turn_msgs: list[dict[str, Any]]) -> str:
    tool_names = ", ".join(
        tc.get("function", {}).get("name", "?")
        for tc in turn_msgs[0].get("tool_calls", [])
    ) if turn_msgs and turn_msgs[0].get("role") == "assistant" else "reply"
    tail = ""
    for m in reversed(turn_msgs):
        content = m.get("content")
        if content:
            tail = content
            break
    tail = tail[:200]
    suffix = "…" if len(tail) == 200 else ""
    return (
        f"[PRUNED {pid} ({tool_names}) — retained for restore(prune_id={pid!r}). "
        f"Tail: {tail}{suffix}]"
    )


async def _tool_prune(*, agent: Agent, prune_ids: list[str] | str | None = None) -> str:
    if isinstance(prune_ids, str):
        prune_ids = [pid.strip() for pid in prune_ids.split(",") if pid.strip()]
    prune_ids = list(prune_ids or [])
    if not prune_ids:
        return (
            "prune(prune_ids=[...]) drops whole committed turns (assistant "
            "message + tool results) and replaces them with a short PRUNED "
            "marker. IDs are listed in your Context Observation as "
            "'prune_id:tools'; use restore(prune_id=...) to bring one back."
        )
    if not agent._turns:
        return "No committed turns to prune."

    requested = [str(pid) for pid in prune_ids]
    invalid = [pid for pid in requested if pid not in agent._turns]
    already = [pid for pid in requested if pid in agent._pruned]
    pending = [pid for pid in requested if pid in agent._turns and pid not in agent._pruned]

    if not pending:
        notes = []
        if already:
            notes.append(f"already pruned (use restore): {already}")
        if invalid:
            notes.append(f"unknown ids (see Context Observation): {invalid}")
        return "Nothing to prune. " + "; ".join(notes)

    remove: dict[int, str] = {}
    for pid in pending:
        for m in agent._turns[pid]:
            remove[id(m)] = pid

    existing_marker_by_id = {
        id(info["marker"]): pid
        for pid, info in agent._prune_markers.items()
    }

    new_messages: list[dict[str, Any]] = []
    marker_for: dict[str, dict[str, Any]] = {}
    i = 0
    idx = 0
    messages = agent._messages
    while i < len(messages):
        m = messages[i]
        pid = remove.get(id(m))
        if pid is None:
            new_messages.append(m)
            old_pid = existing_marker_by_id.get(id(m))
            if old_pid is not None:
                agent._prune_markers[old_pid]["index"] = idx
            i += 1
            idx += 1
            continue
        turn_len = len(agent._turns[pid])
        marker = {
            "role": "assistant",
            "content": _make_prune_marker(pid, agent._turns[pid]),
        }
        marker_for[pid] = {"marker": marker, "index": idx}
        new_messages.append(marker)
        i += turn_len
        idx += 1

    agent._messages = new_messages
    for pid in pending:
        agent._pruned.add(pid)
        agent._prune_markers[pid] = marker_for[pid]

    chars_saved = sum(
        len(_json.dumps(m)) for pid in pending for m in agent._turns[pid]
    )
    evicted = agent.evict_pruned_overflow()
    agent.emit_activity(ActivityEvent(
        agent_id=agent.id,
        event_type=ActivityEventType.COMPRESSION,
        data={
            "turns_pruned": pending,
            "chars_saved": chars_saved,
            "turns_evicted": evicted,
        },
    ))
    notes = []
    if invalid:
        notes.append(f"unknown ids (see Context Observation): {invalid}")
    if already:
        notes.append(f"already pruned (use restore): {already}")
    if evicted:
        notes.append(
            f"old retained turns permanently discarded "
            f"(retention cap {agent.max_pruned_retained}): {evicted}"
        )
    suffix = ("; " + "; ".join(notes)) if notes else ""
    return (
        f"Pruned turns {pending} ({len(pending)} turns, ~{chars_saved} chars "
        f"removed from context). Replaced with PRUNED markers. "
        f"Use restore(prune_id=...) to bring one back.{suffix}"
    )


async def _tool_restore(*, agent: Agent, prune_id: str) -> str:
    prune_id = str(prune_id)
    entry = agent._prune_markers.get(prune_id)
    if entry is None:
        return (f"Nothing to restore for {prune_id!r}: it is not currently pruned "
                f"(or was evicted and is no longer retained).")
    turn_msgs = agent._turns[prune_id]
    marker = entry["marker"]
    messages = agent._messages
    target_idx: int | None = None

    stored_idx = entry.get("index")
    if stored_idx is not None and 0 <= stored_idx < len(messages) and messages[stored_idx] is marker:
        target_idx = stored_idx
    else:
        for j, m in enumerate(messages):
            if m is marker:
                target_idx = j
                break
    if target_idx is None:
        return (f"Cannot restore {prune_id!r}: its PRUNED marker is no longer present "
                f"in the context (likely removed by compression or eviction).")

    agent._messages = messages[:target_idx] + turn_msgs + messages[target_idx + 1:]
    for pid, info in agent._prune_markers.items():
        if pid == prune_id:
            continue
        idx = info.get("index")
        if idx is not None and idx > target_idx:
            info["index"] = idx + (len(turn_msgs) - 1)
    agent._pruned.discard(prune_id)
    agent._prune_markers.pop(prune_id, None)

    chars = sum(len(_json.dumps(m)) for m in turn_msgs)
    n_tools = len(turn_msgs) - 1
    return (
        f"Restored turn {prune_id} (assistant + {n_tools} tool result(s), "
        f"~{chars} chars) at its original position."
    )


async def _tool_converse(*, agent: Agent, agent_id: str, message: str) -> str:
    target = agent.get_other_agent(agent_id)
    if not target:
        return f"Error: no agent found with ID {agent_id}"
    if target.task.status not in (TaskStatus.completed, TaskStatus.running):
        return (
            f"Error: agent {agent_id} status is "
            f"'{target.task.status.value}', cannot converse"
        )

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
    registry.register(TOOL_PRUNE_DEF, _tool_prune)
    registry.register(TOOL_RESTORE_DEF, _tool_restore)
    registry.register(TOOL_CONVERSE_DEF, _tool_converse)
    registry.register(TOOL_READ_ARTIFACT_DEF, _tool_read_artifact)
