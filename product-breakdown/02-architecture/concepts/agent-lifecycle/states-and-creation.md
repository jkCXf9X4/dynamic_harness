# Agent States & Creation

Every agent's task moves through a fixed set of states, and every agent is
created by the Runtime — never instantiated directly outside tests.

## State Machine

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

## State Transitions

| From | To | Trigger | By |
|------|----|---------|-----|
| — | `pending` | `Task` created | User / Parent Agent |
| `pending` | `running` | `runtime.delegate()` | Runtime |
| `running` | `completed` | `agent.report()` | Agent (via tool call) |
| `running` | `escalated` | `agent.escalate()` | Agent (via tool call) |
| `running` | `failed` | `agent.fail()` | Agent (via tool call or safety limit) |

## Creation

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

At creation the agent has an ID, task, runtime reference, and optional parent;
an empty children list; no messages (the conversation hasn't started); and its
iteration counter at 0.
