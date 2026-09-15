from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from ..policies.process import BashSafetyPolicy
from .process import _kill_process_group
from .registry import ToolDef

if TYPE_CHECKING:
    from ..tool_context import ToolContext


TOOL_RESULT_BASH_DEF = ToolDef(
    name="result_bash",
    description=(
        "Run a shell command over a cached tool-result snapshot WITHOUT re-running "
        "the tool that produced it. The snapshot text is piped to the command's "
        "stdin, so you can apply your full bash vocabulary (rg, grep, jq, awk, "
        "wc -l, sort, tail, python3 -c '...') to probe a large saved output. Pass "
        "the result_id from an earlier tool result's footer. Never re-executes the "
        "producing tool, so searching effective tool results in seconds even when "
        "the work was expensive. Piping only reads the snapshot; the producing "
        "tool is NOT called again. An unknown result_id (evicted or the agent "
        "resumed) returns a clear error: call the producing tool again for a "
        "fresh result. WARNING: the command is executed as arbitrary shell code "
        "WITHOUT a sandbox (same security boundary as the bash tool) — it can "
        "read/write the host filesystem, access the network, and run as the "
        "invoking user."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "result_id": {
                "type": "string",
                "description": "Handle returned by an earlier tool call's cached-result footer.",
            },
            "command": {
                "type": "string",
                "description": "Shell command; the snapshot text is piped to its stdin (e.g. 'rg -i pattern | head -50', 'wc -l', 'python3 -c \"for l in __import__(\"sys\").stdin: ...\"').",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in milliseconds (default 120000)",
            },
        },
        "required": ["result_id", "command"],
    },
)


async def result_bash(
    *, ctx: ToolContext, result_id: str, command: str, timeout: int = 120000
) -> str:
    """Run a shell command over a cached snapshot's text (piped to stdin)."""
    text = ctx.result_store.get(result_id)
    if text is None:
        return (
            f"Error: unknown result_id '{result_id}' — the snapshot was evicted "
            "or the agent was reset/resumed (the result cache is in-memory only). "
            "Call the producing tool again (without result_id) to get a fresh copy."
        )

    command, workdir = BashSafetyPolicy.resolve_workdir(command, None)
    if not command:
        return (
            f"(no-op) snapshot {result_id}: {len(text)} chars, "
            f"{len(text.splitlines())} lines"
        )
    cwd = Path(workdir) if workdir else ctx.generated_root

    # Always run through a shell so pipelines (`rg x | head -5`) work naturally.
    proc = await asyncio.create_subprocess_exec(
        "sh", "-c", command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        start_new_session=True,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(text.encode()), timeout=timeout / 1000
        )
    except asyncio.TimeoutError:
        await _kill_process_group(proc)
        return (
            f"Error: command timed out after {timeout}ms (the whole process "
            f"group was killed). Pass a larger 'timeout' (ms) parameter or "
            f"narrow the filter."
        )
    except asyncio.CancelledError:
        # Agent cancelled mid-command (kill/resume/reset): take the process
        # group down before re-raising so no subprocess is orphaned.
        await _kill_process_group(proc)
        raise
    result = ""
    if stdout:
        result += stdout.decode(errors="replace")
    if stderr:
        result += f"\n(STDERR)\n{stderr.decode(errors='replace')}"
    return result.strip() or "(no output)"