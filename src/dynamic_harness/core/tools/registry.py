from __future__ import annotations

import json as _json
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from pydantic import BaseModel

if TYPE_CHECKING:
    from ...core.agent import Agent


ToolFunc = Callable[..., Awaitable[str]]


class ToolDef(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]


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
