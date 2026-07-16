---
title: "Tools Reference"
category: api
module: dynamic_harness.core.capabilities
classes:
  - ToolDef
  - ToolCall
  - ToolResult
  - ToolRegistry
summary: >
  Complete reference for all 15 built-in tools, their OpenAPI schemas,
  implementations, and the ToolRegistry API for registering custom tools.
related:
  - api/runtime.md
  - api/agent.md
  - guides/extending-tools.md
---

# Tools

```python
from dynamic_harness.core.capabilities import ToolDef, ToolCall, ToolResult, ToolRegistry
```

## ToolRegistry

The central registry that stores tool definitions and implementations.

```python
registry = ToolRegistry()

# Register a tool
registry.register(tool_def: ToolDef, fn: ToolFunc) -> None

# Look up
registry.get(name: str) -> tuple[ToolDef, ToolFunc] | None

# Execute (called by agent loop)
await registry.execute(name, tool_call_id, agent, **kwargs) -> ToolResult

# Get OpenAI function-calling schemas
registry.openai_schemas() -> list[dict]

# List registered tool names
registry.list_tools() -> list[str]
```

### Data Types

```python
class ToolDef(BaseModel):
    name: str              # Tool identifier
    description: str       # Human-readable description
    input_schema: dict     # JSON Schema for parameters

class ToolCall(BaseModel):
    id: str                # Tool call ID from LLM
    name: str              # Tool name
    arguments: dict        # Parsed arguments

class ToolResult:
    tool_call_id: str      # Echoed from ToolCall
    content: str           # Tool output as text
```

## Tool Table

| # | Tool | Parameters | Terminal? | Category |
|---|------|-----------|-----------|----------|
| 1 | `read` | `path: str` | No | Filesystem |
| 2 | `write` | `path: str, content: str` | No | Filesystem |
| 3 | `glob` | `pattern: str` | No | Filesystem |
| 4 | `grep` | `pattern: str, include?: str, path?: str` | No | Filesystem |
| 5 | `bash` | `command: str, timeout?: int` | No | Shell |
| 6 | `webfetch` | `url: str` | No | Network |
| 7 | `edit` | `path: str, old_string: str, new_string: str` | No | Filesystem |
| 8 | `delegate` | `description: str, role?: str, system_prompt?: str` | No | Orchestration |
| 9 | `report` | `summary: str, artifact_ids?: list[str], confidence?: float` | **Yes** | Terminal |
| 10 | `escalate` | `issue: str` | **Yes** | Terminal |
| 11 | `fail` | `error: str` | **Yes** | Terminal |
| 12 | `ask` | `question: str` | No | I/O |
| 13 | `compress` | *(none)* | No | Context |
| 14 | `converse` | `agent_id: str, message: str` | No | Communication |
| 15 | `read_artifact` | `artifact_id: str` | No | Artifact |

Terminal tools (report, escalate, fail) set the agent's task status and stop the tool-calling loop.

---

## Individual Tool Reference

### 1. `read` — Read a file

```json
{
  "name": "read",
  "parameters": {
    "path": { "type": "string", "description": "Absolute or relative file path" }
  },
  "required": ["path"]
}
```

**Implementation:** `Path(path).read_text()` — returns file contents as string.

**Errors:** FileNotFoundError if path doesn't exist.

---

### 2. `write` — Write content to a file

```json
{
  "name": "write",
  "parameters": {
    "path": { "type": "string", "description": "Absolute or relative file path" },
    "content": { "type": "string", "description": "Content to write" }
  },
  "required": ["path", "content"]
}
```

**Returns:** `"Wrote {N} bytes to {path}"`

---

### 3. `glob` — List files matching a pattern

```json
{
  "name": "glob",
  "parameters": {
    "pattern": { "type": "string", "description": "Glob pattern (e.g. **/*.py)" }
  },
  "required": ["pattern"]
}
```

**Implementation:** Uses Python's `glob.glob(pattern, recursive=True)`. Filters results through `.gitignore` if present (via `pathspec`). Returns sorted JSON array of file paths.

---

### 4. `grep` — Search file contents with regex

```json
{
  "name": "grep",
  "parameters": {
    "pattern": { "type": "string", "description": "Regex pattern to search for" },
    "include": { "type": "string", "description": "Glob pattern to filter files (e.g. *.py)" },
    "path": { "type": "string", "description": "Directory to search in (default: current)" }
  },
  "required": ["pattern"]
}
```

**Returns:** JSON array of `"file:line: content"` strings. Capped at 200 results. Uses `rglob` for recursive search.

---

### 5. `bash` — Execute a shell command

```json
{
  "name": "bash",
  "parameters": {
    "command": { "type": "string", "description": "Shell command to execute" },
    "timeout": { "type": "integer", "description": "Timeout in milliseconds (default 30000)" }
  },
  "required": ["command"]
}
```

**Implementation:** `asyncio.create_subprocess_shell()` with stdout/stderr capture. Kills process on timeout. Returns combined stdout + stderr.

---

### 6. `webfetch` — Fetch URL content

```json
{
  "name": "webfetch",
  "parameters": {
    "url": { "type": "string", "description": "Fully qualified URL to fetch" }
  },
  "required": ["url"]
}
```

**Implementation:** `httpx.AsyncClient.get(url, timeout=30)`. Raises on non-2xx status.

---

### 7. `edit` — Find-and-replace in a file

```json
{
  "name": "edit",
  "parameters": {
    "path": { "type": "string", "description": "File path to edit" },
    "old_string": { "type": "string", "description": "Text to find and replace" },
    "new_string": { "type": "string", "description": "Replacement text" }
  },
  "required": ["path", "old_string", "new_string"]
}
```

**Implementation:** Reads file, replaces first occurrence of `old_string` with `new_string`, writes back. Returns error if `old_string` not found.

---

### 8. `delegate` — Create and run a sub-agent

```json
{
  "name": "delegate",
  "parameters": {
    "description": { "type": "string", "description": "Description of the task for the sub-agent" },
    "role": { "type": "string", "description": "Optional role tag scoping the sub-agent's focus" },
    "system_prompt": { "type": "string", "description": "Optional custom system prompt override" }
  },
  "required": ["description"]
}
```

This is the core orchestration tool. It:
1. Creates a child `Agent` with the given description + role
2. Runs the child to completion (`await child.run()`)
3. Returns status, summary, artifact IDs, and confidence

**Returns:**
```
Delegated to agent abc123def456. Status: completed
Summary: Found 3 HIGH-severity issues in auth.py...
Artifact IDs: /tmp/security_findings.json
Confidence: 0.95
```

**Critical:** The return value is a preview summary only. The parent **must** verify by reading the child's artifact files. Blind synthesis from the return value is an anti-pattern.

---

### 9. `report` — Complete agent work *(terminal)*

```json
{
  "name": "report",
  "parameters": {
    "summary": { "type": "string", "description": "Summary of findings" },
    "artifact_ids": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Artifact IDs to attach"
    },
    "confidence": {
      "type": "number",
      "description": "Optional confidence score (0.0 = uncertain, 1.0 = certain)"
    }
  },
  "required": ["summary"]
}
```

Terminates the agent. The Runtime saves an artifact + commit.

---

### 10. `escalate` — Escalate to parent *(terminal)*

```json
{
  "name": "escalate",
  "parameters": {
    "issue": { "type": "string", "description": "Description of the issue" }
  },
  "required": ["issue"]
}
```

Terminates the agent with `TaskStatus.escalated`.

---

### 11. `fail` — Report failure *(terminal)*

```json
{
  "name": "fail",
  "parameters": {
    "error": { "type": "string", "description": "Error message" }
  },
  "required": ["error"]
}
```

Terminates the agent with `TaskStatus.failed`.

---

### 12. `ask` — Ask the user a question

```json
{
  "name": "ask",
  "parameters": {
    "question": { "type": "string", "description": "The question to present to the user" }
  },
  "required": ["question"]
}
```

**Implementation:** Uses `input()` to prompt the user via stdin. Blocks until response.

---

### 13. `compress` — Compress conversation context

```json
{
  "name": "compress",
  "parameters": {},
  "required": []
}
```

**Implementation:** Calls the LLM with a compression prompt to summarize all prior messages. Replaces the full conversation history with `[system prompt] + [compressed summary]`. Itself costs ~5K–15K tokens but saves much more in future turns.

**When:** Context > ~50 messages, or >15 turns in the tool loop.

---

### 14. `converse` — Message another agent

```json
{
  "name": "converse",
  "parameters": {
    "agent_id": { "type": "string", "description": "ID of the target agent" },
    "message": { "type": "string", "description": "Message or instruction for the target agent" }
  },
  "required": ["agent_id", "message"]
}
```

**Implementation:** Resumes the target agent via `target.continue_with_input(message)`. Returns the target's latest assistant response and status. Only works on agents with `completed` or `running` status.

---

### 15. `read_artifact` — Read an artifact by ID

```json
{
  "name": "read_artifact",
  "parameters": {
    "artifact_id": { "type": "string", "description": "The ID of the artifact to read" }
  },
  "required": ["artifact_id"]
}
```

**Implementation:** Looks up the artifact in `ArtifactStore`. Returns all non-empty view levels (headline, summary_200, summary_1000, technical, full_report, raw_data).

---

## Custom Tools

```python
from dynamic_harness.core.capabilities import ToolDef, ToolRegistry

async def my_tool(*, agent, param1: str, param2: int = 0) -> str:
    return f"Processed {param1} with {param2}"

my_def = ToolDef(
    name="my_tool",
    description="Does something useful",
    input_schema={
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "First parameter"},
            "param2": {"type": "integer", "description": "Second parameter"},
        },
        "required": ["param1"],
    },
)

runtime.tool_registry.register(my_def, my_tool)
```

Tool functions receive the calling `agent` as a keyword argument (for accessing `agent.id`, `agent.task`, `agent._runtime`, etc.) plus the declared parameters from the schema.

## Initialization

Default tools are registered by `register_default_tools()` which is called in `Runtime.__init__()`. For programmatic use:

```python
from dynamic_harness.core.capabilities import register_default_tools

registry = ToolRegistry()
register_default_tools(registry)
```