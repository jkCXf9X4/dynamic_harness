---
title: "Agent API Reference"
category: api
module: dynamic_harness.core.agent
class: Agent
summary: >
  The core agent class. One agent loop shared by all agents — receives a task,
  enters a tool-calling loop with the LLM, delegates to children, and terminates
  via report/escalate/fail.
related:
  - api/runtime.md
  - api/task.md
  - api/tools.md
  - concepts/agent-lifecycle.md
---

# Agent

```python
from dynamic_harness.core.agent import Agent
```

The **Agent** is the core unit of execution. Every agent runs the same loop: receive a task, call tools via the LLM, delegate subtasks to children, verify results, and terminate. Agents are disposable — after `report()` they carry no state forward.

## Constructor

```python
Agent(
    agent_id: str,              # 12-char hex UUID
    task: Task,                 # The work this agent performs
    runtime: Runtime,           # Central orchestrator
    parent: Agent | None = None, # Parent agent (None for root)

    system_prompt: str | None = None,  # Override default AGENT_SYSTEM_PROMPT
    safety_max_iterations: int = 500,  # Max turns before force-fail
    repeated_call_limit: int = 5,      # Repeated identical calls before force-fail
)
```

**Note:** Agents should be created via `runtime.delegate()` or `agent.delegate()` — never instantiated directly outside of tests.

### Properties

```python
agent.id: str                    # 12-char hex ID
agent.task: Task                 # The assigned task (status updates in place)
agent.parent: Agent | None       # Parent agent
agent.children: list[Agent]      # Child agents
agent.llm: LLMProvider | None    # LLM from runtime (read-only)
agent.guidelines: str            # AGENT_SYSTEM_PROMPT text
```

## Execution

### `async run() -> None`

The main entry point. Runs the agent to completion:

1. Formats the task description (with optional `[ROLE]` tag)
2. Prepares messages: system prompt + user message
3. Enters `_run_loop()` — the tool-calling loop
4. Terminates when `report()`, `escalate()`, or `fail()` is called

**No-LLM mode:** If `runtime._llm` is `None`, the agent immediately calls `report()` with the task description as the summary.

```python
agent = runtime.delegate(Task(description="Read foo.py and count lines"))
await agent.run()
# agent.task.status == TaskStatus.completed
```

### `async _run_loop() -> None`

The core tool-calling loop. Not called directly — invoked by `run()`.

Each iteration:
1. Appends a **Context Observation** (turn count, message count, token estimate)
2. Calls `llm.generate_with_tools(messages, tools)`
3. If the response has tool calls: executes them via `ToolRegistry.execute()`, feeds results back
4. If the response has no tool calls: treats content as the report summary
5. Safety checks: max iterations, repeated-call detection

### `async continue_with_input(user_message: str) -> None`

Resume an agent with new input. Appends a user message and re-enters the tool loop.

```python
# After agent completes, use converse to ask follow-up
await completed_agent.continue_with_input("What about the error handling in main.py?")
```

## Delegation

### `delegate(description, agent_type=None, role=None, system_prompt=None, **metadata) -> Agent`

Create a child agent for a subtask. Returns immediately — the child is NOT run yet.

```python
child = agent.delegate(
    description="You are a Security Auditor. Run bandit on src/ and report HIGH severity findings.",
    role="Security Auditor",
)
await child.run()
```

The child's `Task` is created with `parent_id=agent.task.id`. The child is added to `agent.children` and registered in the runtime's task graph.

## Termination Methods

All three set the task status and deliver the event to the Runtime.

### `report(payload: ReportPayload) -> None`

Signals successful completion. The Runtime saves an artifact + commit.

```python
agent.report(ReportPayload(
    task_id=agent.task.id,
    summary="Found 3 HIGH-severity issues in auth.py",
    artifact_ids=["/tmp/security_findings.json"],
    confidence=0.9,
))
```

### `escalate(issue: str, **context) -> None`

Escalate to parent when blocked. Task status → `escalated`.

```python
agent.escalate("Cannot access auth.py: Permission denied", file="src/auth.py")
```

### `fail(error: str, trace: str | None = None) -> None`

Report irrecoverable failure. Task status → `failed`.

```python
agent.fail("Required dependency 'bandit' is not installed")
```

## Budget

### `request_more_budget(current_usage: int, requested: int, reason: str) -> None`

Signal the runtime that the agent needs more token budget.

## Safety Invariants

| Mechanism | Default | Behavior on Violation |
|-----------|---------|----------------------|
| `safety_max_iterations` | 500 | `fail()` with safety limit message |
| `repeated_call_limit` | 5 | `fail()` if 5 identical tool call batches in a row |
| Context observation | Every turn | Informs LLM about turn/message/token counts |

## AGENT_SYSTEM_PROMPT

The `AGENT_SYSTEM_PROMPT` constant defines the mandatory workflow all agents follow:

```
ANALYZE → DECOMPOSE → DELEGATE → VERIFY → SYNTHESIZE → TERMINATE
```

Key rules enforced in the prompt:
- **Decompose first, act second** — never call tools before planning
- **Delegate aggressively** — 2+ tool calls → delegate to sub-agent
- **Verify before synthesizing** — read child artifacts, confirm they exist
- **Context health** — compress at 50+ messages, delegate at 5–15 turns
- **Artifact-driven communication** — write findings to disk, reference by path

See `docs/agent_methodology_guidelines.md` for the full detailed methodology.

## Internal State

```python
agent._messages: list[dict] | None          # Conversation history
agent._iteration: int                        # Current turn count
agent._recent_batches: deque                 # Sliding window for repeated-call detection
agent._last_report: ReportPayload | None     # Set on terminal report()
agent._last_failure: Failure | None          # Set on terminal fail()
```