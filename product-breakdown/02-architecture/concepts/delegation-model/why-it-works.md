# Why Recursive Decomposition Works

## Fresh Context Economics

| Approach | Context | Quality | Cost |
|----------|---------|---------|------|
| Monolithic agent, 20 turns | Bloat, stale context | Degraded | High (per-turn scaling) |
| 3 sub-agents × 3 turns each | Fresh per sub-task | High (focused) | Delegation overhead ~3K tokens |

A delegation costs ~3K tokens overhead. Doing it yourself for 3+ turns at 2K+
tokens/turn is both more expensive and lower quality.

## Context Encapsulation

Agents know only their parent, their children, and their assigned task. They
never see siblings, cousins, the global task graph, work in other branches, or
historical context from ancestors. This forces each agent to be self-contained
and prevents cross-contamination.

## Parallelism

Independent sub-tasks are delegated in the same tool-calling turn. The delegate
tool runs each child to completion before returning, so the parent gets all
results back in one response cycle.
