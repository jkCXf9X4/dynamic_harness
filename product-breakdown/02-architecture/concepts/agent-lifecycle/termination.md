# Termination & Resumption

Three terminal paths, all triggered by tool calls, plus automatic safety
force-fails. After termination the agent's history and last report stay
accessible.

## `report()` — Success

```python
agent.report(ReportPayload(
    task_id=agent.task.id,
    summary="Added JWT expiry validation. 3 tests pass.",
    artifact_ids=["/tmp/auth_fix.txt"],
    confidence=0.95,
))
```

Results in `task.status = completed`; the artifact is saved to `ArtifactStore`;
a commit is created in `Repository`; and `on_report` handlers fire.

## `escalate()` — Blocked

```python
agent.escalate("Cannot access auth.py: Permission denied")
```

Results in `task.status = escalated` and `on_escalation` handlers firing.

## `fail()` — Error

```python
agent.fail("Required dependency not installed")
```

Results in `task.status = failed` and `on_failure` handlers firing.

## Force-Fail (Safety)

```python
# Two automatic failure triggers:

# 1. Max iterations exceeded
if self._iteration > self._safety_max_iterations:  # default: 500
    self.fail(f"Safety limit reached ({self._safety_max_iterations} iterations)")

# 2. Repeated identical tool calls
# If 5 identical batches of tool calls in a row:
self.fail("Repeated identical tool calls 5 times in a row...")

# Pure monitoring tools (status / usage) are exempt: a parent polling its
# running children's status while they self-heal is waiting, not looping.
# Turns composed solely of those tools are not counted toward loop detection.
```

## Post-Termination

The conversation history (`_messages`) and final report (`_last_report`) remain
accessible, enabling:

- **Parent verification:** parent reads `child._last_report`
- **Converse:** `agent.continue_with_input()` resumes a completed agent
- **Debugging:** `_messages` holds the full conversation trace

## Resuming Agents (converse)

```python
await agent.continue_with_input("What about the error handling in login.py?")
```

This appends the user message to the existing `_messages`, resets status to
`running`, and re-enters `_run_loop()`. The agent continues from where it left
off with full access to its previous conversation.
