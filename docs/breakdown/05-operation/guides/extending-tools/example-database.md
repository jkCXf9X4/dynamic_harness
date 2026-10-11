---
id: INFO-104
type: info
title: "Example: Database Tool"
summary: A complete read-only SQL query tool: ToolDef, async handler, and registration.
date: 2026-09-23
status: current
---

# Example: Database Tool

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

## Owns
- A complete read-only SQL query tool example.

## Excludes
- ToolDef field schema: `INFO-108`.
- Tool shape guidance: `INFO-102`.
