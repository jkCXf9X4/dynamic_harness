# Minimal Custom Tool

```python
from dynamic_harness.core.tools import ToolDef, ToolRegistry

async def my_hello_tool(*, ctx, name: str) -> str:
    return f"Hello, {name}! (from agent {ctx.agent_id[:8]})"

tool_def = ToolDef(
    name="hello",
    description="Say hello to someone by name",
    input_schema={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Name to greet",
            },
        },
        "required": ["name"],
    },
)

runtime.tool_registry.register(tool_def, my_hello_tool)
```

## Tool Function Signature

```python
async def tool_name(*, ctx, param1: type, param2: type = default) -> str:
    # ctx (ToolContext) parameter is injected automatically
    # All schema parameters appear as keyword arguments
    return "Tool output as string"
```

### Key Rules

1. **`ctx` (a `ToolContext`) is always the first keyword argument** — the registry builds it from the calling agent. It exposes `ctx.agent_id`, `ctx.task_id`, `ctx.generated_root`, `ctx.gitignore_filter()`, `ctx.workspace_lock(path)`, `ctx.repo_lock()`, `ctx.llm`, `ctx.emit_activity(event)`, `ctx.report(payload)`, `ctx.escalate(issue)`, `ctx.fail(error)`, `ctx.run_delegate_tool(...)`, `ctx.get_other_agent(id)`, `ctx.artifact_store`, and the context-management calls (`ctx.compress()`, `ctx.prune(...)`, `ctx.restore(...)`).
2. **Return type is always `str`** — the string becomes the tool result fed back to the LLM.
3. **Async required** — all tool functions must be `async def`.
4. **Parameters match the schema** — parameter names and types must correspond to `input_schema.properties`.
