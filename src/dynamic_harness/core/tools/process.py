from __future__ import annotations

import asyncio
import shlex as _shlex
from pathlib import Path
from typing import TYPE_CHECKING

from .registry import ToolDef

if TYPE_CHECKING:
    from ...core.tool_context import ToolContext


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


_READ_ONLY_COMMANDS = {
    "ls", "cat", "head", "tail", "grep", "find", "pwd", "which",
    "python3", "python", "echo", "env", "printenv", "wc", "sort", "uniq",
}
_READ_ONLY_GIT_SUBCOMMANDS = {
    "status", "log", "show", "diff", "branch", "config", "stash", "blame", "rev-parse",
}


def _is_read_only(args: list[str]) -> bool:
    """Heuristic: does this command only read, so no repo lock is needed?"""
    if not args:
        return True
    base = Path(args[0]).name
    if base in _READ_ONLY_COMMANDS:
        return True
    if base == "git" and len(args) > 1 and args[1] in _READ_ONLY_GIT_SUBCOMMANDS:
        return True
    return False


async def bash(*, ctx: ToolContext, command: str, timeout: int = 30000) -> str:
    try:
        args = _shlex.split(command)
    except ValueError as e:
        return f"Error: invalid command syntax: {e}"

    cwd = ctx.generated_root
    repo_lock = None
    if args and not _is_read_only(args):
        repo_lock = ctx.repo_lock()
        await repo_lock.acquire()
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout / 1000)
        except asyncio.TimeoutError:
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
    finally:
        if repo_lock:
            repo_lock.release()
