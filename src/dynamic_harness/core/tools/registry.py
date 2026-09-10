from __future__ import annotations

import json as _json
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from pydantic import BaseModel

from ..policies.result_cache import ResultCachePolicy

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
    "delegate", "converse", "kill", "status", "resume", "ask", "read_artifact", "usage",
    "report", "escalate", "fail",
    "compress", "prune", "restore",
    "plan", "checkpoint",
    "result_read",
})


ROLE_TOOL_OVERRIDES: dict[str, frozenset[str]] = {
    "orchestrator": ORCHESTRATOR_ALLOWED_TOOLS,
}


def tools_for_role(role: str | None) -> frozenset[str] | None:
    """Return the explicit allow-list for a role, or None for no restriction."""
    if role is None:
        return None
    return ROLE_TOOL_OVERRIDES.get(role)


# Tools whose output is NEVER cached behind a result handle. These mutate
# state, move execution, or drive control flow (or are views over other
# results like result_read itself) — caching them would let a later
# `result_read` resurrect a side effect or present a meaningless snapshot.
# Kept for back-compat; the set now lives with ResultCachePolicy.
NON_CACHEABLE_TOOLS: frozenset[str] = ResultCachePolicy.DEFAULT_NON_CACHEABLE


class ToolResult:
    def __init__(self, tool_call_id: str, content: str, result_id: str | None = None) -> None:
        self.tool_call_id = tool_call_id
        self.content = content
        # Handle into the agent's ResultStore for the full (untruncated) output
        # of this call, or None for tools that are never cached. Read-only:
        # the `result_read` tool pages it; the model calls the work tool again
        # to get a fresh result.
        self.result_id = result_id


class ToolRegistry:
    def __init__(
        self,
        cache_policy: ResultCachePolicy | None = None,
    ) -> None:
        self._tools: dict[str, tuple[ToolDef, ToolFunc]] = {}
        self._cache_policy: ResultCachePolicy = cache_policy or ResultCachePolicy()

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

        if name == "result_read":
            # `result_read` IS the paging mechanism: its token_offset/token_limit
            # are its OWN parameters (they slice an existing snapshot), not the
            # generic truncation knobs. Forward them untouched and return the
            # tool's output verbatim — no snapshot, no re-slicing.
            try:
                content = await fn(
                    ctx=ctx, token_limit=token_limit, token_offset=token_offset,
                    **kwargs,
                )
            except Exception as e:
                return ToolResult(
                    tool_call_id=tool_call_id, content=f"Error executing {name}: {e}"
                )
            if content is None:
                content = ""
            elif not isinstance(content, str):
                content = str(content)
            return ToolResult(tool_call_id=tool_call_id, content=content)

        try:
            content = await fn(ctx=ctx, **kwargs)
        except Exception as e:
            return ToolResult(tool_call_id=tool_call_id, content=f"Error executing {name}: {e}")

        # Tools are allowed to return None or non-string values; normalize them
        # here so the truncation/slicing below never raises on a falsy body.
        if content is None:
            content = ""
        elif not isinstance(content, str):
            content = str(content)

        # Every cacheable tool's FULL output is snapshotted behind an opaque
        # handle before any truncation, so the model can page later parts with
        # the read-only `result_read` tool instead of re-running slow work.
        # Cacheability + truncation/footer policy live in ResultCachePolicy.
        result_id = self._cache_policy.snapshot(ctx.result_store, name, content)
        content = self._cache_policy.render(
            content,
            token_limit=token_limit,
            token_offset=token_offset,
            name=name,
            result_id=result_id,
        )
        return ToolResult(tool_call_id=tool_call_id, content=content, result_id=result_id)

    def openai_schemas(self, role: str | None = None) -> list[dict]:
        allowed = tools_for_role(role)
        result: list[dict] = []
        for td, _ in self._tools.values():
            if allowed is not None and td.name not in allowed:
                continue
            schema = dict(td.input_schema)
            schema["properties"] = dict(schema.get("properties", {}))
            if td.name != "result_read":
                # result_read declares its own token_offset/token_limit (they are
                # its paging knobs, not the generic truncation knobs).
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
