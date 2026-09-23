# Delegation Model

Recursive task decomposition: parent agents break work into independent
sub-tasks, delegate to child agents, verify results, and synthesize a combined
output — the core mechanism that keeps contexts shallow and quality high.

## Owns
- The mandatory orchestration workflow (ANALYZE → … → TERMINATE)
- The delegation decision tree and leaf-vs-orchestrator heuristic
- The parent↔child contract (briefs, roles, reports) and failure handling
- Streaming (opt-in) delegation and context-health monitoring
- Rationale: fresh-context economics, encapsulation, parallelism

## Excludes
- Agent states, run loop, safety → [agent-lifecycle/](../agent-lifecycle/README.md)
- Artifact/commit mechanics → [artifact-system/](../artifact-system/README.md)
- Failure recovery machinery → [self-healing/](../self-healing/README.md)

## Contents
- [workflow.md](workflow.md) — the six-step mandatory workflow
- [delegation-decisions.md](delegation-decisions.md) — when to delegate; leaf vs orchestrator
- [streaming.md](streaming.md) — opt-in streaming delegation
- [why-it-works.md](why-it-works.md) — fresh-context economics, encapsulation, parallelism
- [parent-child-contract.md](parent-child-contract.md) — briefs, mission command, roles, reports
- [failure-handling.md](failure-handling.md) — recovering from failed children
- [context-health.md](context-health.md) — observation thresholds

See `../../../../docs/references/mission_command_rationale.md` and
`../../../../docs/api/agent.md`, `runtime.md`, `tools.md`.
