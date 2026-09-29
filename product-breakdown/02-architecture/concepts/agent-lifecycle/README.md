---
title: Agent Lifecycle
summary: "The complete lifecycle of an agent — from creation through execution to termination: task states, the tool-calling loop, safety invariants, terminatio…"
---

# Agent Lifecycle

The complete lifecycle of an agent — from creation through execution to
termination: task states, the tool-calling loop, safety invariants, termination
paths, and the Agent/Runtime split.

## Owns
- Task state machine and transitions
- Agent creation and the run loop (initialization, tool-calling, context observation)
- Termination paths (report/escalate/fail/force-fail) and post-termination resume
- Safety invariants, timeout layering, token usage tracking
- Agent vs Runtime responsibilities

## Excludes
- Delegation orchestration → [delegation-model/](../delegation-model/README.md)
- Artifact/commit mechanics → [artifact-system/](../artifact-system/README.md)
- Recovery policy → [self-healing/](../self-healing/README.md)

See `../../../../docs/api/agent.md`, `runtime.md`, `task.md`.

## Contents

<!-- pb:index:start -->
- **INFO-029** [The Run Loop](run-loop.md) — initializes the conversation, then executes the tool-calling loop until a terminal tool fires
- **INFO-030** [Safety Invariants](safety-invariants.md) — Three independent timeouts apply to different resource types
- **INFO-031** [Agent States & Creation](states-and-creation.md) — Every agent's task moves through a fixed set of states, and every agent is created by the Runtime — never instantiated directly outside tests
- **INFO-032** [Termination & Resumption](termination.md) — Three terminal paths, all triggered by tool calls, plus automatic safety force-fails. After termination the agent's history and last report stay acces…
- **INFO-033** [Usage & Responsibilities](usage-and-responsibilities.md) — The Runtime records per-agent consumption after each LLM response
<!-- pb:index:end -->
