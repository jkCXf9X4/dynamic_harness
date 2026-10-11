---
id: INFO-105
type: info
title: "Example: Notification Tool"
summary: A complete notification tool that writes to a JSONL log: ToolDef, async handler, and registration.
date: 2026-09-23
status: current
---

# Example: Notification Tool

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

## Owns
- A complete notification tool example that writes to a JSONL log.

## Excludes
- ToolDef field schema: `INFO-108`.
- Tool shape guidance: `INFO-102`.
