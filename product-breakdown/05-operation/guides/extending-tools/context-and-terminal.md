# ToolContext & Terminal Tools

## Accessing Runtime Services

The `ctx` parameter gives access to everything a tool is allowed to see — it is
a narrow public façade, so tools cannot reach into agent/runtime private state:

```python
async def my_tool(*, ctx, query: str) -> str:
    # Read from artifact store (owned by the runtime)
    artifacts = ctx.artifact_store

    # Get the LLM
    llm = ctx.llm

    # Emit an activity event (streamed to events.jsonl by the CLI/layout)
    ctx.emit_activity(event)

    # File sandbox root (where read/write tools operate)
    root = ctx.generated_root

    return f"Processed query: {query}"
```

> Note: to keep the boundary clean, tools do **not** receive the `Agent`
> directly. If you need agent/task/usage data in a tool, surface it as a public
> accessor on `Agent` and add a matching accessor on `ToolContext`.

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
