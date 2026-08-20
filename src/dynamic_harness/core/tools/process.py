from __future__ import annotations

import asyncio
import re
import shlex as _shlex
from pathlib import Path
from typing import TYPE_CHECKING

from .registry import ToolDef

if TYPE_CHECKING:
    from ...core.tool_context import ToolContext


TOOL_BASH_DEF = ToolDef(
    name="bash",
    description="Execute a command and return its output. Use for building, running tests, "
                "git operations, or any CLI task. Supports a leading `cd <dir> &&` prefix "
                "and an explicit workdir; when the command uses shell operators (&&, ||, |, "
                ";, etc.) it runs through a shell so chained commands work. Each call is a "
                "fresh process with no persistent working directory — use cd prefixes or the "
                "workdir parameter to run in another directory.",
    input_schema={
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Command with arguments to execute. A leading 'cd <dir> && ' prefix sets the working directory; shell chains (&&, |, ;) are supported."},
            "timeout": {"type": "integer", "description": "Timeout in milliseconds (default 30000)"},
            "workdir": {"type": "string", "description": "Working directory to run the command in (overrides a leading cd prefix; default is the sandbox/generated root)"},
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

# Shell metacharacters that require a shell to interpret (&&, ||, |, ;, <, >,
# backtick). A leading `cd <dir> &&` is handled separately and stripped before
# this check so a bare `cd X && ls` chain still funnels into the shell path.
_SHELL_META = re.compile(r"[|&;<>`]")

# Leading `cd <dir> && ` (or a bare `cd <dir>`). Captured as the working
# directory; the remainder is the command to run.
_LEADING_CD = re.compile(r"^\s*cd\s+(\S+)\s*(?:&&\s*)?")


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


def _resolve_workdir(command: str, workdir: str | None) -> tuple[str, str | None]:
    """Pull a leading ``cd <dir> &&`` prefix into the working directory.

    Stripping it here means a common agent habit — ``cd /path && ls ...`` — stops
    failing as an ``exec`` ``[Errno 2] No such file or directory: 'cd'`` error,
    which was churning the conversation prefix with identical repeated failures
    and (because each retry re-ran the whole chain) thinning the provider prompt
    cache. Returns ``(command_without_cd, resolved_workdir)``.
    """
    m = _LEADING_CD.match(command or "")
    if not m:
        return command, (workdir or None)
    resolved = workdir or m.group(1)
    rest = (command[m.end():]).strip()
    if not rest:
        return "", resolved
    return rest, resolved


async def bash(*, ctx: ToolContext, command: str, timeout: int = 30000, workdir: str | None = None) -> str:
    command, workdir = _resolve_workdir(command, workdir)
    if not command:
        return f"(no-op) Working directory would be: {workdir or ctx.generated_root}"

    cwd = Path(workdir) if workdir else ctx.generated_root
    repo_lock = None

    # Shell operators present -> interpret via a shell so `cd X && ...`, pipes,
    # and chained commands actually run instead of producing a hard exec error.
    use_shell = bool(_SHELL_META.search(command))

    # Heuristic read-only check (kept even in shell mode: base the decision on
    # the first command token, which is generally the mutating one).
    try:
        tokens = _shlex.split(command)
    except ValueError:
        tokens = []
    if tokens and not _is_read_only(tokens):
        repo_lock = ctx.repo_lock()
        await repo_lock.acquire()
    try:
        if use_shell:
            proc = await asyncio.create_subprocess_exec(
                "sh", "-c", command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
        else:
            try:
                args = _shlex.split(command)
            except ValueError as e:
                return f"Error: invalid command syntax: {e}"
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
