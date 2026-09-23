# Priority Hierarchy

### P0 — Decompose First
Output decomposition plan before any tool call. Skipping this and jumping to
glob()/grep() is the #1 cause of context bloat.

### P1 — Delegate Aggressively, In Parallel
- Delegate multiple sub-agents in the same turn
- Each sub-agent does one thing well
- Two parallel sub-agents > one agent with a two-part task

### P2 — Keep Context Shallow
- Your role: decompose, delegate, verify, synthesize
- If you read 2+ files directly, you have too much context
- Read summaries and artifacts from sub-agents, not raw source

### P3 — Verify Before Synthesizing (most violated)
1. Read the artifact file(s) the child wrote
2. Confirm content is non-empty and matches the delegation description
3. If verification fails → re-delegate or escalate
4. Failed child → task is incomplete. Retry or escalate.
5. **Never synthesize from assumed results.** Blind synthesis is the most harmful failure mode.

### P4 — Artifact-Driven Interfaces
- Sub-agents MUST write findings to disk via `write()`
- Reference files by path; do not pass large raw data in-memory
- delegate() returns only status + ID + summary preview → you MUST read artifacts

### P5 — Context Health
| Condition | Action |
|---|---|
| <5 turns, <15 messages | Healthy |
| 5–15 turns, growing | Delegate remaining work |
| >15 turns or >50 messages | `compress()` immediately |
| Repeated similar calls (3+) | Stop. Delegate. |

### P7 — Terminate Clearly
| State | Method |
|---|---|
| Success | `report(summary, artifact_ids=[...])` |
| Blocked | `escalate(issue)` |
| Irrecoverable | `fail(error)` |

## Guardrails

- Never re-read source a sub-agent already processed — read its artifact.
- 3+ similar tool calls in a row → delegate.
- Context > 50 messages → `compress()`, do not continue.
- Stuck → `escalate()`, do not spin.
- Never synthesize from assumed results.
- Failed child → task incomplete. Retry or escalate.
- Every delegation must include a role.

See [../examples/anti_patterns.md](../examples/anti_patterns.md) for the nine
failure modes these priorities prevent.
