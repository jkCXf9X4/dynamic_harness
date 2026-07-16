---
title: "Agent Lifecycle"
category: concept
summary: >
  The complete lifecycle of an agent — from creation through execution to
  termination. Covers task states, the tool-calling loop, safety invariants,
  termination paths, and the relationship between agents and the Runtime.
related:
  - api/agent.md
  - api/runtime.md
  - api/task.md
  - concepts/delegation-model.md
---

# Agent Lifecycle

Every agent in Dynamic Harness follows the same lifecycle — from creation through execution to termination. Understanding this lifecycle is essential for debugging, extending, and reasoning about agent behavior.

## State Machine

An agent's task goes through these states:

```
                    runtime.delegate()
  [Task created] ──────────────────────→ pending
                                              │
                                     agent.run()
                                              │
                                              ▼
                                         running
                                     ╱     │     ╲
                        report() ╱  escalate()  ╲ fail()
                                ▼       ▼         ▼
                          completed  escalated   failed
```

### State Transitions

| From | To | Trigger | By |
|------|----|---------|-----|
| — | `pending` | `Task` created | User / Parent Agent |
| `pending` | `running` | `runtime.delegate()` | Runtime |
| `running` | `completed` | `agent.report()` | Agent (via tool call) |
| `running` | `escalated` | `agent.escalate()` | Agent (via tool call) |
| `running` | `failed` | `agent.fail()` | Agent (via tool call or safety limit) |

##Detailed Lifecycle

### 1. Creation

```python
# An agent is created by the Runtime — never instantiated directly (outside tests)
agent = runtime.delegate(task, parent=parent_agent)

# What happens:
#   - 12-char hex ID is generated
#   - Agent is registered in _agents dict
#   - Entry is added to _task_graph
#   - If parent exists, linked in parent.children and task_graph
#   - task.status = TaskStatus.running
```

At creation, the agent has:
- An ID, task, runtime reference, and optional parent
- Empty children list
- No messages (conversation hasn't started)
- Iteration counter at 0

### 2. Execution (run)

```python
await agent.run()
```

#### Phase 1: Initialization

```python
async def run(self) -> None:
    llm = self.llm  # Get LLM from runtime
    if not llm:
        # No-LLM mode: immediately report
        self.report(ReportPayload(
            task_id=self.task.id,
            summary=f"Agent {self.id} executed: {self.task.description}",
        ))
        return

    # Format the user message
    user_message = self.task.description
    if self.task.role:
        user_message = f"[ROLE] {self.task.role}\n\n[TASK] {self.task.description}"

    # Build initial messages
    self._messages = [
        {"role": "system", "content": self._system_prompt or AGENT_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]
    self._iteration = 0
    self._recent_batches = deque(maxlen=self.repeated_call_limit)
    await self._run_loop()
```

#### Phase 2: The Tool-Calling Loop

Each iteration:

```
┌─────────────────────────────────────────┐
│ 1. Increment turn counter               │
│ 2. Safety check: max iterations?        │ → fail() if exceeded
│ 3. Append Context Observation           │
│ 4. Call llm.generate_with_tools()       │
│ 5. Record usage, trace request          │
│                                         │
│ Has tool calls?                         │
│   YES → Execute each tool               │
│          ├── Feed results as messages   │
│          ├── Check for terminal status   │
│          └── Safety: repeated calls?    │ → fail() if 5 identical
│   NO  → Treat content as report         │
│          └── report(content)            │
└─────────────────────────────────────────┘
```

#### Context Observation

Before each turn, the agent appends a system message:

```
[Context Observation]
Turn: 7
Messages in context: 21
Estimated prompt tokens this agent: 12000
Your task: Audit auth.py for security issues
```

This observation helps the LLM monitor its own context health and make informed decisions about delegation vs continuation vs compression.

### 3. Termination

Three terminal paths, all triggered by tool calls:

#### `report()` — Success

```python
agent.report(ReportPayload(
    task_id=agent.task.id,
    summary="Added JWT expiry validation. 3 tests pass.",
    artifact_ids=["/tmp/auth_fix.txt"],
    confidence=0.95,
))
```

Results in:
- `task.status = completed`
- Artifact saved to `ArtifactStore`
- Commit created in `Repository`
- `on_report` handlers fired

#### `escalate()` — Blocked

```python
agent.escalate("Cannot access auth.py: Permission denied")
```

Results in:
- `task.status = escalated`
- `on_escalation` handlers fired

#### `fail()` — Error

```python
agent.fail("Required dependency not installed")
```

Results in:
- `task.status = failed`
- `on_failure` handlers fired

#### Force-Fail (Safety)

```python
# Two automatic failure triggers:

# 1. Max iterations exceeded
if self._iteration > self._safety_max_iterations:  # default: 500
    self.fail(f"Safety limit reached ({self._safety_max_iterations} iterations)")

# 2. Repeated identical tool calls
# If 5 identical batches of tool calls in a row:
self.fail("Repeated identical tool calls 5 times in a row...")
```

### 4. Post-Termination

After termination, the agent's conversation history (`_messages`) and final report (`_last_report`) remain accessible. This enables:

- **Parent verification:** Parent reads `child._last_report`
- **Converse:** `agent.continue_with_input()` resumes a completed agent
- **Debugging:** `_messages` contains the full conversation trace

## Resuming Agents (converse)

A completed agent can be resumed with new input:

```python
await agent.continue_with_input("What about the error handling in login.py?")
```

This:
1. Appends the user message to the existing `_messages`
2. Resets status to `running`
3. Re-enters `_run_loop()`

The agent continues from where it left off, with full access to its previous conversation.

## Safety Invariants

| Mechanism | Default | Effect |
|-----------|---------|--------|
| `safety_max_iterations` | 500 | Prevents infinite loops |
| `repeated_call_limit` | 5 | Prevents LLM from getting stuck on one tool |
| Context observation | Every turn | Enables LLM to self-monitor context health |
| `compress()` tool | Available at any time | LLM can compress its context to avoid rot |

## Token Usage Tracking

Throughout the lifecycle, the Runtime tracks per-agent token consumption:

```python
# Recorded after each LLM response:
runtime.record_usage(
    agent_id,
    prompt_tokens=response.usage.prompt_tokens,
    completion_tokens=response.usage.completion_tokens,
    message_count=len(messages),
)

# Accessible at any time:
usage = runtime.get_usage(agent.id)
# {"prompt_tokens": 15000, "completion_tokens": 3000, "total_tokens": 18000, "message_count": 25}
```

## Agent vs Runtime Responsibilities

| Concern | Agent | Runtime |
|---------|-------|---------|
| Tool calling loop | ✓ | — |
| Tool execution | — | ✓ (ToolRegistry) |
| Task status management | — | ✓ |
| Artifact creation | — | ✓ |
| Commit creation | — | ✓ |
| Event dispatching | — | ✓ |
| Token tracking | — | ✓ |
| Delegation (creating children) | ✓ | ✓ (registration) |
| Safety limits | ✓ | — |
| Context management | ✓ | — |

Agents are self-contained execution units. The Runtime is a shared infrastructure layer. This separation enables the actor-model design — agents share nothing except via the Runtime's controlled interfaces.