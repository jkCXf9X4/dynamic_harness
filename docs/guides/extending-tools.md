---
title: "Extending Tools"
category: guide
difficulty: advanced
summary: >
  How to register custom tools in the ToolRegistry. Covers tool definition
  schemas, implementation signatures, accessing the calling agent, and
  integration patterns.
related:
  - api/tools.md
  - api/runtime.md
  - guides/programmatic-usage.md
---

# Extending Tools

Custom tools extend what agents can do. Tools are registered with the `ToolRegistry` and become available to all agents the next time they enter the tool-calling loop.

## Minimal Custom Tool

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

All tool functions follow this pattern:

```python
async def tool_name(*, ctx, param1: type, param2: type = default) -> str:
    # ctx (ToolContext) parameter is injected automatically
    # All schema parameters appear as keyword arguments
    return "Tool output as string"
```

### Key Rules

1. **`ctx` (a `ToolContext`) is always the first keyword argument** — the registry builds it from the calling agent. It exposes `ctx.agent_id`, `ctx.task_id`, `ctx.generated_root`, `ctx.gitignore_filter()`, `ctx.workspace_lock(path)`, `ctx.repo_lock()`, `ctx.llm`, `ctx.emit_activity(event)`, `ctx.report(payload)`, `ctx.escalate(issue)`, `ctx.fail(error)`, `ctx.run_delegate_tool(...)`, `ctx.get_other_agent(id)`, `ctx.artifact_store`, and the context-management calls (`ctx.compress()`, `ctx.prune(...)`, `ctx.restore(...)`).
2. **Return type is always `str`** — the string becomes the tool result fed back to the LLM
3. **Async required** — all tool functions must be `async def`
4. **Parameters match the schema** — parameter names and types must correspond to `input_schema.properties`

## Accessing Runtime Services

The `ctx` parameter gives access to everything a tool is allowed to see — it is a
narrow public façade, so tools cannot reach into agent/runtime private state:

```python
async def my_tool(*, ctx, query: str) -> str:
    # Read from artifact store (owned by the runtime)
    artifacts = ctx.artifact_store

    # Get the LLM
    llm = ctx.llm

    # Emit an activity event (for the CLI/TUI/logs)
    ctx.emit_activity(event)

    # File sandbox root (where read/write tools operate)
    root = ctx.generated_root

    return f"Processed query: {query}"
```

> Note: to keep the boundary clean, tools do **not** receive the `Agent` directly.
> If you need agent/task/usage data in a tool, surface it as a public accessor on
> `Agent` and add a matching accessor on `ToolContext`.

## Tool Definition Schema

The `ToolDef` uses standard JSON Schema:

```python
ToolDef(
    name="tool_name",        # Unique identifier
    description="...",       # Shown to the LLM in function descriptions
    input_schema={
        "type": "object",
        "properties": {
            "param": {
                "type": "string",  # JSON Schema type
                "description": "Description for the LLM",
            },
            "optional_param": {
                "type": "integer",
                "description": "An optional integer",
            },
        },
        "required": ["param"],  # List of required property names
    },
)
```

Supported JSON Schema types:
- `"string"` → `str`
- `"integer"` → `int`
- `"number"` → `float`
- `"boolean"` → `bool`
- `"array"` → `list`
- `"object"` → `dict`

## Terminal Tools

Tools that stop the agent loop must call one of the agent's terminal methods:

```python
async def my_approve(*, ctx, decision: str) -> str:
    if decision == "approved":
        ctx.report(ReportPayload(
            task_id=ctx.task_id,
            summary=f"Work approved by agent {ctx.agent_id[:8]}",
        ))
        return "Approved and completed"
    else:
        ctx.fail(f"Decision rejected: {decision}")
        return "Rejected"
```

## Example: Database Tool

```python
import sqlite3

TOOL_DB_QUERY = ToolDef(
    name="db_query",
    description="Execute a read-only SQL query against the project database",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "SELECT query to execute"},
            "limit": {"type": "integer", "description": "Max rows to return (default 100)"},
        },
        "required": ["query"],
    },
)

async def _tool_db_query(*, ctx, query: str, limit: int = 100) -> str:
    conn = sqlite3.connect("file:data.db?mode=ro", uri=True)
    try:
        import json
        rows = conn.execute(query).fetchmany(limit)
        return json.dumps([dict(zip([c[0] for c in conn.description], row)) for row in rows], indent=2)
    finally:
        conn.close()

runtime.tool_registry.register(TOOL_DB_QUERY, _tool_db_query)
```

## Example: Notification Tool

```python
import json

TOOL_NOTIFY = ToolDef(
    name="notify",
    description="Send a notification when a task completes",
    input_schema={
        "type": "object",
        "properties": {
            "channel": {"type": "string", "description": "Notification channel (slack, email, log)"},
            "message": {"type": "string", "description": "Notification message"},
            "severity": {"type": "string", "description": "info | warn | error"},
        },
        "required": ["channel", "message"],
    },
)

async def _tool_notify(*, ctx, channel: str, message: str, severity: str = "info") -> str:
    # Write notification to a log file (example)
    log_path = ctx.generated_root or Path("/tmp")
    notifications = log_path / "notifications.jsonl"

    entry = {
        "agent_id": ctx.agent_id,
        "channel": channel,
        "severity": severity,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    with open(notifications, "a") as f:
        f.write(json.dumps(entry) + "\n")

    return f"Notification sent to {channel}: {message[:100]}"

runtime.tool_registry.register(TOOL_NOTIFY, _tool_notify)
```

## Registration Timing

Tools can be registered at any time, but they only become visible to agents when the agent next enters `_run_loop()` (i.e., the next tool-calling turn). For agents already in a loop, new tools won't appear until they complete and restart.

### At Runtime Startup

```python
runtime = Runtime(...)
runtime.tool_registry.register(my_tool_def, my_tool_fn)
# All subsequent agents will have the tool
```

### Conditionally

```python
if feature_enabled:
    runtime.tool_registry.register(feature_tool_def, feature_tool_fn)
```

### Per-Agent

If you want a tool available only to specific agents, register before delegating and deregister after. But note: the ToolRegistry is shared — deregistering affects all agents. For per-agent tools, consider overriding the agent's tool list via a custom Agent subclass.

## Unregistering Tools

The `ToolRegistry` supports removing a tool by name:

```python
runtime.tool_registry.unregister("my_tool")

# Verify it's gone
assert "my_tool" not in runtime.tool_registry.list_tools()
```

Note: the registry is shared across agents, so unregistering affects all agents.
For per-agent tool sets, consider overriding the tool list via a custom Agent
subclass or a dedicated registry. If you need a fully custom set of defaults,
you can also build your own registry:

```python
from dynamic_harness.core.tools import ToolRegistry, register_default_tools

my_registry = ToolRegistry()
register_default_tools(my_registry)
my_registry.register(my_tool_def, my_tool_fn)
```

## Best Practices

1. **Descriptive tool names** — `db_query` not `db`
2. **Detailed descriptions** — The LLM uses descriptions to decide when to call your tool
3. **Validate inputs** — Return error strings (not exceptions) for bad inputs
4. **Keep it simple** — One tool = one clear responsibility
5. **Return structured output** — JSON-formatted strings are easiest for the LLM to parse