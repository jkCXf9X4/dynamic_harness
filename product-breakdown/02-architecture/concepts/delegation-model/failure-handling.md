---
id: INFO-040
type: info
title: Failure Handling
summary: Never ignore failed children and synthesize partial results. A failed child means the task is incomplete
date: 2026-09-23
status: current
---

# Failure Handling

| Failure | Recovery |
|---------|----------|
| Child returns `Status: failed` | Read failure reason. Retry with better description, or escalate |
| Child reports success but artifact empty | `converse(child_id, "...")`. Re-delegate if needed |
| Child hit safety limits | Task was too broad. Re-delegate with narrower scope |
| Multiple children all fail | Decomposition likely wrong. Escalate |
| Child escalated | Read escalation context. Resolve or pass up |

Never ignore failed children and synthesize partial results. A failed child
means the task is incomplete.

See `self-healing` for the runtime recovery policy
and the `resume`/`kill` tools.
