from __future__ import annotations

import glob as _glob
import json as _json
import re as _re
from pathlib import Path
from typing import TYPE_CHECKING

from .registry import ToolDef

if TYPE_CHECKING:
    from ...core.tool_context import ToolContext

MAX_READ_CHARS = 400_000


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


def is_hidden(path: str | Path) -> bool:
    p = Path(path)
    for part in p.parts:
        if part.startswith("."):
            return True
    return False


def sandbox_root(ctx: ToolContext) -> Path:
    """The workspace an agent is allowed to operate in (read/glob/grep)."""
    return ctx.generated_root or Path.cwd()


def resolve_safe_path(path: str, ctx: ToolContext) -> Path:
    sandbox = ctx.generated_root or Path.cwd()
    p = Path(path)
    if p.is_absolute():
        resolved = p.resolve()
    else:
        resolved = (sandbox / p).resolve()
    if sandbox not in resolved.parents and resolved != sandbox:
        raise ValueError(f"Path '{path}' is outside the workspace")
    return resolved


def is_hidden(path: str | Path) -> bool:
    p = Path(path)
    for part in p.parts:
        if part.startswith("."):
            return True
    return False


async def read(*, ctx: ToolContext, path: str) -> str:
    try:
        safe = resolve_safe_path(path, ctx)
    except ValueError as e:
        return f"Error: {e}"
    text = safe.read_text()
    if len(text) > MAX_READ_CHARS:
        text = text[:MAX_READ_CHARS] + (
            f"\n\n[TRUNCATED: file larger than {MAX_READ_CHARS} chars; "
            f"read the first {MAX_READ_CHARS}. Use token_offset to paginate.]"
        )
    return text


async def write(*, ctx: ToolContext, path: str, content: str) -> str:
    try:
        safe = resolve_safe_path(path, ctx)
    except ValueError as e:
        return f"Error: {e}"
    lock = await ctx.workspace_lock(str(safe))
    async with lock:
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


async def glob(*, ctx: ToolContext, pattern: str) -> str:
    search = Path(pattern)
    if not search.is_absolute():
        search = sandbox_root(ctx) / search
    matches = _glob.glob(str(search), recursive=True)
    _filter = ctx.gitignore_filter()
    filtered = [m for m in matches if not _filter(m) and not is_hidden(m)]
    if filtered:
        return _json.dumps(sorted(filtered), indent=2)
    visible = [m for m in matches if not is_hidden(m)]
    return _json.dumps(sorted(visible), indent=2)


async def grep(*, ctx: ToolContext, pattern: str, include: str | None = None, path: str | None = None) -> str:
    if path:
        search_path = Path(path)
        if not search_path.is_absolute():
            search_path = sandbox_root(ctx) / search_path
    else:
        search_path = sandbox_root(ctx)
    if not search_path.is_dir():
        return f"Error: {search_path} is not a directory"
    _filter = ctx.gitignore_filter()
    matches: list[str] = []
    errors: int = 0
    for f in search_path.rglob(include or "*"):
        if not f.is_file():
            continue
        if is_hidden(f):
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


async def edit(*, ctx: ToolContext, path: str, old_string: str, new_string: str) -> str:
    try:
        safe = resolve_safe_path(path, ctx)
    except ValueError as e:
        return f"Error: {e}"
    lock = await ctx.workspace_lock(str(safe))
    async with lock:
        content = safe.read_text()
        if old_string not in content:
            return f"Error: old_string not found in {path}"
        new_content = content.replace(old_string, new_string, 1)
        safe.write_text(new_content)
    return f"Replaced in {path}"
