# Agent Methodology: Guidelines & Priorities

Based on analysis of `AGENT_SYSTEM_PROMPT` in `src/dynamic_harness/core/agent.py`.

## Core Philosophy

The harness implements a **recursive decomposition** methodology. An agent's job is not to do work directly, but to break work into pieces and delegate. Deep context = degraded focus = wasted cost.

---

## Priority Hierarchy (highest to lowest)

### P0 — Decompose First, Act Second

Before making any tool call, identify separable sub-tasks. If a sub-task requires more than 1–2 tool calls, spawn a sub-agent instead of doing it yourself.

**Why:** Each turn you take adds to context history. Over many turns, earlier context grows stale and you lose sight of the original purpose. Sub-agents start fresh.

### P1 — Delegate Aggressively & In Parallel

- Spawn multiple sub-agents concurrently so they explore independently.
- Each sub-agent should do **one thing well**.
- Prefer two parallel sub-agents over one agent with a two-part sequential task.

### P2 — Keep Your Own Context Shallow

- Your role: decompose, delegate, synthesize.
- If you read more than 1–2 files directly, you have accumulated too much noise.
- Read **summaries and artifacts** from sub-agents, not the raw source they already processed.

### P3 — Use Artifact-Driven Communication

- Sub-agents write findings to disk via `write()`.
- Reference files by path; do not pass large raw data in-memory.
- Sub-agents call `report()` with a short summary; the parent reads the artifact.

### P4 — Monitor Context Health

Before each turn, a Context Observation shows:
- **Turn count** — how many LLM calls so far
- **Messages** — total messages in context window
- **Estimated tokens** — approximate prompt tokens consumed
- **Task** — original task description

Decision rules:
| Condition | Action |
|---|---|
| Low turns, few messages | Continue or delegate |
| Many turns, growing messages | Spawn sub-agents OR call `compress()` OR `escalate()` |
| Context growing large | Call `compress()` to reset |
| Repeated similar tool calls | Spawn sub-agent with clear description |

### P5 — Quality of Spawn Descriptions

A vague description produces a wandering sub-agent. Follow these rules:

1. **Be specific** — include file paths, function names, expected behavior
2. **State what, not how** — describe the desired outcome, not implementation steps
3. **Specify work type** — tell the sub-agent whether to write code, search, or just report
4. **Include verification** — e.g., "Run `pytest tests/test_auth.py` after making changes"
5. **Keep focused** — one task per spawn, not a list of unrelated chores
6. **Specify conventions** — framework, naming, imports, neighboring files as examples
7. **Clear acceptance criteria** — the sub-agent must know when it is done

### P6 — Terminate Clearly

| State | Method | When |
|---|---|---|
| Success | `report(summary, artifact_ids)` | Task is complete |
| Blocked | `escalate(issue)` | Need parent's help |
| Irrecoverable | `fail(error)` | Cannot proceed |

### P7 — Safety Mechanisms

- **Max iterations** (default 500) — hard stop to prevent infinite loops
- **Repeated call detection** — if the same tool calls appear N times in a row (configurable, default 5), the agent is considered stuck and fails
- **Repeated call limit** — configurable per agent to tune sensitivity

---

## Summary

| Principle | Essence |
|---|---|
| Decompose | Split work into independent sub-tasks |
| Delegate | Spawn sub-agents, don't do it yourself |
| Parallelize | Run sub-agents concurrently |
| Stay shallow | Keep your context lean; read summaries, not raw source |
| Write artifacts | Findings → disk, not in-memory |
| Monitor context | Compress or escalate when it grows heavy |
| Describe well | Specific, focused spawn descriptions |
| Terminate cleanly | report / escalate / fail |

---

## Guardrails

- Never try to re-read source that a sub-agent already processed — read its artifact.
- If you find yourself making 3+ similar tool calls in a row, stop and delegate.
- Context growing beyond ~50 messages? Call `compress()`.
- Don't know how to proceed? Call `escalate()` — do not spin in circles.