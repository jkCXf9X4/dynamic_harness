---
title: "Task Model Reference"
category: api
module: dynamic_harness.core.task
summary: >
  Pydantic models for the task system: Task, TaskStatus, ReportPayload,
  Escalation, Failure, DelegateRequest, and BudgetRequest.
related:
  - api/runtime.md
  - api/agent.md
---

# Task & Related Models

```python
from dynamic_harness.core.task import (
    Task, TaskStatus, ReportPayload, Escalation,
    Failure, DelegateRequest, BudgetRequest,
)
```

## `TaskStatus`

```python
class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    escalated = "escalated"
```

## `Task`

The primary unit of work. Represents what an agent must do.

```python
class Task(BaseModel):
    id: str              # uuid4 hex, 12 chars, auto-generated
    description: str     # What the agent should do
    role: str | None     # Scope constraint (e.g. "Security Auditor")
    system_prompt: str | None  # Custom system prompt override
    parent_id: str | None     # Parent task ID
    status: TaskStatus         # Current state, defaults to pending
    created_at: datetime       # UTC, auto-generated
    metadata: dict             # Arbitrary key-value pairs
```

### Lifecycle

```
pending → running → completed | failed | escalated
```

Status is updated by the Runtime:
- `pending` → `running` on `runtime.delegate()`
- `running` → `completed` on `runtime.deliver_report()`
- `running` → `failed` on `runtime.deliver_failure()`
- `running` → `escalated` on `runtime.deliver_escalation()`

## `ReportPayload`

The structured output an agent produces when it completes.

```python
class ReportPayload(BaseModel):
    task_id: str           # Must match agent.task.id
    summary: str           # Concrete 1-2 sentence findings
    confidence: float | None  # 0.0 (uncertain) to 1.0 (certain)
    claims: list[str]         # Specific claims made
    next_actions: list[str]   # Suggested follow-ups
    artifact_ids: list[str]   # Paths to artifact files on disk
    questions: list[str]      # Open questions for the user/parent
```

**Example:**
```python
ReportPayload(
    task_id="abc123def456",
    summary="Added JWT expiry validation to auth.py. 3 tests pass.",
    confidence=0.95,
    claims=["auth.py:45 adds expiry check", "3 tests pass in test_auth.py"],
    artifact_ids=["/tmp/auth_fix_summary.txt"],
)
```

## `DelegateRequest`

Wraps a Task for delegation with optional budget.

```python
class DelegateRequest(BaseModel):
    task: Task
    budget: int | None
```

## `BudgetRequest`

Sent by an agent requesting more token budget.

```python
class BudgetRequest(BaseModel):
    task_id: str
    current_usage: int   # Tokens used so far
    requested: int       # Additional tokens requested
    reason: str          # Why more budget is needed
```

## `Escalation`

Sent when an agent is blocked and needs parent intervention.

```python
class Escalation(BaseModel):
    task_id: str
    issue: str                  # Description of the blocking issue
    context: dict[str, Any]     # Additional diagnostic context
```

## `Failure`

Sent when an agent hits an unrecoverable error.

```python
class Failure(BaseModel):
    task_id: str
    error: str          # Error description
    trace: str | None   # Optional stack trace or debug info
```