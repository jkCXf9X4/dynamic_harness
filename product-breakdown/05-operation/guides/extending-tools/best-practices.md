# Best Practices

A well-shaped tool is cheap for the LLM to select, call, and recover from.
Keep the schema and description as tight as the implementation.

1. **Descriptive tool names** — `db_query` not `db`.
2. **Detailed descriptions** — the LLM uses descriptions to decide when to call your tool.
3. **Validate inputs** — return error strings (not exceptions) for bad inputs.
4. **Keep it simple** — one tool = one clear responsibility.
5. **Return structured output** — JSON-formatted strings are easiest for the LLM to parse.

Prefer returning a short error string over raising: the model can read a failure
message and retry, but an exception aborts the turn.
