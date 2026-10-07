---
title: Delegation Model
summary: "Recursive task decomposition: parent agents break work into independent sub-tasks, delegate to child agents, verify results, and synthesize a combined…"
---

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

See `../../../../3rd_party/agent_methods_and_tools/src/agent_methods/methods/mission-command/SKILL.md` and

`../../../../docs/api/agent.md`, `runtime.md`, `tools.md`.

## Contents
