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

- `"string"` → `str`
- `"integer"` → `int`
- `"number"` → `float`
- `"boolean"` → `bool`
- `"array"` → `list`
- `"object"` → `dict`
