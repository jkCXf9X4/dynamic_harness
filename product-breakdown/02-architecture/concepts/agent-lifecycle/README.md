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

## Contents
- [states-and-creation.md](states-and-creation.md) — task states, transitions, agent creation
- [run-loop.md](run-loop.md) — initialization, tool-calling loop, context observation
- [termination.md](termination.md) — report/escalate/fail/force-fail, post-termination, resume
- [safety-invariants.md](safety-invariants.md) — safety table and the three timeout layers
- [usage-and-responsibilities.md](usage-and-responsibilities.md) — token tracking, Agent vs Runtime

See `../../../../docs/api/agent.md`, `runtime.md`, `task.md`.
