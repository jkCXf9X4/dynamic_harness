---
title: "Tools Reference"
category: api
module: dynamic_harness.core.tools.registry
classes:
  - ToolDef
  - ToolResult
  - ToolRegistry
summary: >
  Complete reference for all 17 built-in tools, their OpenAPI schemas,
  implementations, and the ToolRegistry API for registering custom tools.
related:
  - api/runtime.md
  - api/agent.md
  - guides/extending-tools.md
---

# Tools

```python
from dynamic_harness.core.tools import ToolDef, ToolResult, ToolRegistry
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
| 9 | `report` | `summary: str, artifact_ids?: list[str], technical_summary?: str, full_report?: str, confidence?: float` | **Yes** | Terminal |
| 10 | `escalate` | `issue: str` | **Yes** | Terminal |
| 11 | `fail` | `error: str` | **Yes** | Terminal |
| 12 | `ask` | `question: str` | No | I/O |
| 13 | `compress` | *(none)* | No | Context |
| 14 | `prune` | `prune_ids?: list[str]` | No | Context |
| 15 | `restore` | `prune_id: str` | No | Context |
| 16 | `converse` | `agent_id: str, message: str` | No | Communication |
| 17 | `kill` | `agent_id: str, reason?: str, recursive?: bool` | No | Orchestration |
| 18 | `status` | `agent_id?: str` | No | Orchestration |
| 19 | `resume` | `agent_id: str, note?: str, strategy?: str` | No | Orchestration |
| 20 | `read_artifact` | `artifact_id: str` | No | Artifact |

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

**Implementation:** `asyncio.create_subprocess_exec()` with stdout/stderr capture. The command is split into arguments via shell-quoting rules — **no shell operators (pipes, redirects, `&&`, `||`, etc.) are supported**. Kills process on timeout. Returns combined stdout + stderr.

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

**Implementation:** `httpx.AsyncClient` streaming GET (validates scheme/host and rejects literal loopback/private addresses), follows up to 3 redirects re-validating each hop, and caps the response at 200 KB. Raises on non-2xx status.

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
2. Batch-delegates with any other `delegate()` calls in the same turn (parallel), running children to completion before returning
3. Returns status, summary, artifact IDs, and confidence as JSON

**Returns (JSON):**
```json
{
  "child_id": "abc123def456",
  "status": "completed",
  "summary": "Found 3 HIGH-severity issues in auth.py...",
  "artifact_ids": ["/tmp/security_findings.json"],
  "confidence": 0.95
}
```
On failure, the JSON includes a `"failure"` field with the failure reason instead of `summary`.

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
    "technical_summary": {
      "type": "string",
      "description": "Optional detailed technical analysis of findings"
    },
    "full_report": {
      "type": "string",
      "description": "Optional complete report with full detail"
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

**Implementation:** The default implementation prompts on stdin via `input()`. The CLI installs its own `ask` handler that routes the question through the terminal prompt (pausing the token counter while it waits).

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

### 14. `prune` — Drop stale turns from context

```json
{
  "name": "prune",
  "parameters": {
    "prune_ids": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Turn ids (from Context Observation 'prune_id:tools') to prune"
    }
  },
  "required": ["prune_ids"]
}
```

**Implementation:** Removes whole committed turns (assistant message + tool results) listed in the Context Observation and replaces them with a short `[PRUNED ...]` marker. The full content is kept in memory and can be recovered via `restore()`. Prefer over `compress()` when only a few turns are stale. The task definition and system prompt are never touched.

---

### 15. `restore` — Bring a pruned turn back

```json
{
  "name": "restore",
  "parameters": {
    "prune_id": { "type": "string", "description": "Turn id to restore, e.g. 't3'" }
  },
  "required": ["prune_id"]
}
```

**Implementation:** Re-inserts a previously pruned turn (assistant message + tool results) back into the context at the location of its PRUNED marker. Returns an error if the turn was already evicted (e.g. by compression or the retention cap).

---

### 16. `converse` — Message another agent

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

**Implementation:** Resumes the target agent via `target.continue_with_input(message)`. Returns the target's latest assistant response and status. Only works on agents with `completed` or `running` status; for a failed/under-delivered child, use the `resume` tool instead.

---

### 17. `kill` — Kill a child agent

```json
{
  "name": "kill",
  "parameters": {
    "agent_id": { "type": "string", "description": "ID of a direct child to kill" },
    "reason": { "type": "string", "description": "Optional reason recorded on the child's failure" },
    "recursive": { "type": "boolean", "description": "Also kill the child's descendants (default false)" }
  },
  "required": ["agent_id"]
}
```

**Implementation:** Cancels the child's in-flight run task and marks it `failed` (with the optional reason), preserving already-written artifacts/commits. Killed agents are flagged `_killed` and excluded from self-heal, so they are never resurrected. Only a child this agent directly delegated may be killed. The result embeds `salvage` — a map of killed agent id → `runtime_snapshot()` — capturing each killed agent's summary, plan (done+pending), and recent in-context progress so the parent can retry.

---

### 18. `status` — Read child status(es) + partial progress

```json
{
  "name": "status",
  "parameters": {
    "agent_id": { "type": "string", "description": "Optional: ID of a direct child to inspect. Omit to list all children." }
  },
  "required": []
}
```

**Implementation:** Returns a snapshot per child (or one child by id): `status`, `outcome` (`running`/`completed`/`failed`/`killed`/`escalated`), `killed`, final `summary` (or failure reason), `artifact_id`, the plan (`done`+`pending` steps, objective, deliverable), `checkpoint_notes`, iterations, and `partial_data` — a bounded tail of the child's recent in-context activity. Each snapshot also carries a `heal` block: the runtime's blunt-vs-rot `diagnosis` (the same signal self-heal uses), `resumes`/`fresh` heal counts already spent on the child, and a `recoverable` boolean. Use it after a child fails/is killed to recover its partial work, then re-delegate with that salvage to retry — or call `resume` on a recoverable child. Restricted to direct children.

---

### 19. `resume` — Resume a failed/under-delivered child

```json
{
  "name": "resume",
  "parameters": {
    "agent_id": { "type": "string", "description": "ID of a direct child to resume" },
    "note": { "type": "string", "description": "Optional corrective instruction appended to the child's resume/fresh prompt" },
    "strategy": { "type": "string", "enum": ["automatic", "resume", "fresh"], "description": "default automatic" }
  },
  "required": ["agent_id"]
}
```

**Implementation:** The parent-driven sibling of the runtime's automatic
self-heal (`Runtime._recover`). The parent chooses when and how to recover a
child that failed or finished without an on-disk deliverable, instead of relying
only on the automatic policy. Guards mirror `kill`/`status` — only direct
children, never an escalated child, never a deliberately-killed child
(`_killed`). Two recovery layers, both budgeted by the child's own heal counts:

- **`resume`** (blunt / force): resumes the SAME child via
  `Runtime.resume(id, message=..., parent=...)`. A healthy (blunt) context keeps
  its prior work and is corrected with a nudge carrying the failure reason and
  the parent's `note`. If the context is rotted (repeated calls / safety stop /
  many iterations) a forced `resume` is *refused* — replaying it would repeat
  the problem — and the parent is told to use `fresh`.
- **`fresh`** (rot / after resume misses): starts a clean worker over the same
  task via `Runtime._fresh_restart`, injecting the failure reason, prior
  artifact ids, and the parent's `note`. Rot is diagnosed identically to
  self-heal via `agent.is_rot()`.

When the child's context was garbage-collected, `Runtime.resume` rebuilds it
from the on-disk checkpoint (a new agent id); the parent's `children` list is
re-pointed at the effective agent. Returns the effective agent's id/status, the
`diagnosis`, `heal_counts` consumed, `healed`, and a summary/artifact id.
Escalations are never resumed.

---

### 20. `read_artifact` — Read an artifact by ID

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
from dynamic_harness.core.tools import ToolDef, ToolRegistry

async def my_tool(*, ctx, param1: str, param2: int = 0) -> str:
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

Tool functions receive a `ToolContext` (`ctx`) — a narrow public interface built
from the calling agent — as a keyword argument, plus the declared parameters from
the schema. To create a `ToolContext` manually for a custom agent, use
`ToolContext(agent)`.

## Initialization

Default tools are registered by `register_default_tools()` which is called in `Runtime.__init__()`. For programmatic use:

```python
from dynamic_harness.core.tools import register_default_tools

registry = ToolRegistry()
register_default_tools(registry)
```