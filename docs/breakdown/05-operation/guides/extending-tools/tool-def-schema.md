---
id: INFO-108
type: info
title: Tool Definition Schema
summary: ToolDef uses standard JSON Schema for input_schema, with a fixed set of supported types.
date: 2026-09-23
status: current
---

# Tool Definition Schema

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

- `"string"` to `str`
- `"integer"` to `int`
- `"number"` to `float`
- `"boolean"` to `bool`
- `"array"` to `list`
- `"object"` to `dict`

## Owns
- ToolDef field shape and supported JSON Schema types.

## Excludes
- Tool shape guidance: `INFO-102`.
- Registration and visibility: `INFO-107`.
