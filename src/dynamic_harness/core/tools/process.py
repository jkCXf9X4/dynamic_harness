from __future__ import annotations

import asyncio
import shlex as _shlex
from typing import TYPE_CHECKING

from .registry import ToolDef

if TYPE_CHECKING:
    from ...core.agent import Agent


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


async def bash(*, agent: Agent, command: str, timeout: int = 30000) -> str:
    try:
        args = _shlex.split(command)
    except ValueError as e:
        return f"Error: invalid command syntax: {e}"

    cwd = agent.generated_root
    repo_lock = None
    if args:
        repo_lock = agent.repo_lock()
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
