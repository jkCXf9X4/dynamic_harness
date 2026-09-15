from __future__ import annotations

import asyncio
import os
import shlex as _shlex
import signal as _signal
from pathlib import Path
from typing import TYPE_CHECKING

from ..policies.process import BashSafetyPolicy
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
                "workdir parameter to run in another directory. WARNING: arbitrary shell "
                "commands are executed WITHOUT a sandbox and can read/write the host "
                "filesystem, access the network, and run as the invoking user — this is a "
                "deliberate security-boundary decision of the harness.",
    input_schema={
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Command with arguments to execute. A leading 'cd <dir> && ' prefix sets the working directory; shell chains (&&, |, ;) are supported."},
            "timeout": {"type": "integer", "description": "Timeout in milliseconds (default 120000)"},
            "workdir": {"type": "string", "description": "Working directory to run the command in (overrides a leading cd prefix; default is the sandbox/generated root)"},
        },
        "required": ["command"],
    },
)


async def _kill_process_group(proc: asyncio.subprocess.Process) -> None:
    """Kill every process in ``proc``'s group (spawned via start_new_session,
    so pgid == proc.pid) and reap it. Kills the grandchildren too — a plain
    ``proc.kill()`` only terminates the direct child, orphaning the actual
    command running underneath a shell. A bounded wait prevents an
    un-terminatable process from wedging the loop forever."""
    try:
        os.killpg(proc.pid, _signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        try:
            proc.kill()
        except ProcessLookupError:
            pass
    try:
        await asyncio.wait_for(proc.wait(), timeout=2.0)
    except asyncio.TimeoutError:
        pass


async def bash(*, ctx: ToolContext, command: str, timeout: int = 120000, workdir: str | None = None) -> str:
    command, workdir = BashSafetyPolicy.resolve_workdir(command, workdir)
    if not command:
        return f"(no-op) Working directory would be: {workdir or ctx.generated_root}"

    cwd = Path(workdir) if workdir else ctx.generated_root
    repo_lock = None

    # Shell operators present -> interpret via a shell so `cd X && ...`, pipes,
    # and chained commands actually run instead of producing a hard exec error.
    use_shell = BashSafetyPolicy.needs_shell(command)

    # Heuristic read-only check (kept even in shell mode: base the decision on
    # the first command token, which is generally the mutating one). Decision
    # lives in BashSafetyPolicy so an MCP bash wrapper reuses the same rule.
    try:
        tokens = _shlex.split(command)
    except ValueError:
        tokens = []
    if tokens and not BashSafetyPolicy.is_read_only(tokens):
        repo_lock = ctx.repo_lock()
        await repo_lock.acquire()
    try:
        if use_shell:
            proc = await asyncio.create_subprocess_exec(
                "sh", "-c", command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                start_new_session=True,
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
                start_new_session=True,
            )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout / 1000)
        except asyncio.TimeoutError:
            await _kill_process_group(proc)
            return (
                f"Error: command timed out after {timeout}ms (the whole process "
                f"group was killed). Pass a larger 'timeout' (ms) parameter for "
                f"long-running commands."
            )
        except asyncio.CancelledError:
            # The agent was cancelled (kill/resume/reset) mid-command: take the
            # process group down before re-raising so the run never orphans a
            # still-running subprocess (e.g. a pip install or test suite).
            await _kill_process_group(proc)
            raise
        result = ""
        if stdout:
            result += stdout.decode(errors="replace")
        if stderr:
            result += f"\n(STDERR)\n{stderr.decode(errors='replace')}"
        return result.strip() or "(no output)"
    finally:
        if repo_lock:
            repo_lock.release()
