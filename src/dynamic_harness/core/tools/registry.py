from __future__ import annotations

import json as _json
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from pydantic import BaseModel

if TYPE_CHECKING:
    from ...core.agent import Agent
    from ...core.tool_context import ToolContext


ToolFunc = Callable[..., Awaitable[str]]


class ToolDef(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]


# Tools an orchestrator IS allowed: orchestration + verification + its own
# context management (compress/prune/restore only manage its own memory).
# Anything else (read/write/glob/grep/edit/bash/webfetch) is worker work that
# an orchestrator physically cannot invoke — closing the "what counts as work"
# loophole in code, not just in prompt text.
ORCHESTRATOR_ALLOWED_TOOLS: frozenset[str] = frozenset({
    "delegate", "converse", "ask", "read_artifact",
    "report", "escalate", "fail",
    "compress", "prune", "restore",
})


ROLE_TOOL_OVERRIDES: dict[str, frozenset[str]] = {
    "orchestrator": ORCHESTRATOR_ALLOWED_TOOLS,
}


def tools_for_role(role: str | None) -> frozenset[str] | None:
    """Return the explicit allow-list for a role, or None for no restriction."""
    if role is None:
        return None
    return ROLE_TOOL_OVERRIDES.get(role)


class ToolResult:
    def __init__(self, tool_call_id: str, content: str) -> None:
        self.tool_call_id = tool_call_id
        self.content = content


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, tuple[ToolDef, ToolFunc]] = {}

    def register(self, tool_def: ToolDef, fn: ToolFunc) -> None:
        self._tools[tool_def.name] = (tool_def, fn)

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> tuple[ToolDef, ToolFunc] | None:
        return self._tools.get(name)

    async def execute(self, name: str, tool_call_id: str, agent: Agent, **kwargs: Any) -> ToolResult:
        token_limit: int = kwargs.pop("token_limit", 100)
        token_offset: int = kwargs.pop("token_offset", 0)

        allowed = tools_for_role(getattr(agent, "role", None))
        if allowed is not None and name not in allowed:
            return ToolResult(
                tool_call_id=tool_call_id,
                content=(
                    f"Error: tool '{name}' is not allowed for role "
                    f"'{getattr(agent, 'role', None)}'. Orchestrators may only use: "
                    f"{', '.join(sorted(allowed))}. Delegate this work instead."
                ),
            )

        entry = self._tools.get(name)
        if not entry:
            return ToolResult(tool_call_id=tool_call_id, content=f"Error: unknown tool '{name}'")
        _, fn = entry
        # Tools receive a ToolContext (built from the agent) rather than the
        # agent itself, preserving the actor boundary.
        from ..tool_context import ToolContext

        ctx = agent if isinstance(agent, ToolContext) else ToolContext(agent)
        try:
            content = await fn(ctx=ctx, **kwargs)
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

    def openai_schemas(self, role: str | None = None) -> list[dict]:
        allowed = tools_for_role(role)
        result: list[dict] = []
        for td, _ in self._tools.values():
            if allowed is not None and td.name not in allowed:
                continue
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
