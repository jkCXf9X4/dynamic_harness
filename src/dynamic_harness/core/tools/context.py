from __future__ import annotations

from typing import TYPE_CHECKING

from ..task import ActivityEvent, ActivityEventType
from .registry import ToolDef

if TYPE_CHECKING:
    from ...core.tool_context import ToolContext


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


async def compress(*, ctx: ToolContext) -> str:
    if not ctx.messages or len(ctx.messages) < 3:
        return "Nothing to compress."
    llm = ctx.llm
    if not llm:
        return "No LLM available for compression."

    result = await ctx.compress()
    ctx.emit_activity(ActivityEvent(
        agent_id=ctx.agent_id,
        event_type=ActivityEventType.COMPRESSION,
        data={
            "before": result.get("before", 0),
            "after": result.get("after", 0),
            "saved": result.get("saved", 0),
        },
    ))
    return result["message"]


async def prune(*, ctx: ToolContext, prune_ids: list[str] | str | None = None) -> str:
    result = ctx.prune(prune_ids)
    assert result is not None
    if result.get("action"):
        ctx.emit_activity(ActivityEvent(
            agent_id=ctx.agent_id,
            event_type=ActivityEventType.COMPRESSION,
            data={
                "turns_pruned": result["turns_pruned"],
                "chars_saved": result["chars_saved"],
                "turns_evicted": result["evicted"],
            },
        ))
    return result["message"]


async def restore(*, ctx: ToolContext, prune_id: str) -> str:
    return ctx.restore(prune_id)
