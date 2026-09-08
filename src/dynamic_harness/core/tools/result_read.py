from __future__ import annotations

from typing import TYPE_CHECKING

from .registry import ToolDef

if TYPE_CHECKING:
    from ...core.tool_context import ToolContext


TOOL_RESULT_READ_DEF = ToolDef(
    name="result_read",
    description=(
        "Read a previously-produced tool result snapshot WITHOUT re-running the "
        "tool. When a read/grep/glob/bash/webfetch/status/read_artifact call is "
        "truncated, its result is cached under a result_id and the footer tells "
        "you how to page it. Pass that result_id here with token_offset/ "
        "token_limit to view other parts of the SAME snapshot — nothing is "
        "re-executed, so paging slow work is free. An unknown result_id (evicted "
        "or the agent resumed) returns a clear error: call the producing tool "
        "again for a fresh result. result_id is always read-only."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "result_id": {
                "type": "string",
                "description": "Handle returned by an earlier tool call's cached-result footer.",
            },
            "token_limit": {
                "type": "integer",
                "description": "Max tokens to return (1 token ≈ 4 chars). Default 100.",
            },
            "token_offset": {
                "type": "integer",
                "description": "Skip this many tokens from the snapshot start. Default 0.",
            },
        },
        "required": ["result_id"],
    },
)


async def result_read(
    *, ctx: ToolContext, result_id: str, token_limit: int = 100, token_offset: int = 0
) -> str:
    """Page an existing cached tool-result snapshot by handle (read-only)."""
    text = ctx.result_store.get(result_id)
    if text is None:
        return (
            f"Error: unknown result_id '{result_id}' — the snapshot was evicted "
            "or the agent was reset/resumed (the result cache is in-memory only). "
            "Call the producing tool again (without result_id) to get a fresh copy."
        )

    char_limit = max(1, token_limit * 4)
    char_offset = max(0, token_offset * 4)
    total_chars = len(text)
    if char_offset >= total_chars:
        return (
            f"(offset beyond content length of result {result_id}; "
            f"it has {total_chars // 4} tokens total)"
        )
    content = text[char_offset:]
    if len(content) > char_limit:
        content = content[:char_limit] + (
            f"\n... ({token_limit} tokens shown, {total_chars // 4} total. "
            f"Continue: result_read(result_id=\"{result_id}\", "
            f"token_offset={token_offset + token_limit})."
        )
    return content