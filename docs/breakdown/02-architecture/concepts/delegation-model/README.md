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

<!-- pb:index:start -->
<!-- GENERATED FILE — do not edit. Regenerate with pb-registers. -->
- **INFO-038** [Context Health Monitoring](context-health.md) — The agent loop includes a Context Observation before each turn
- **INFO-039** [When to Delegate](delegation-decisions.md) — Before every tool call, an agent decides
- **INFO-040** [Failure Handling](failure-handling.md) — Never ignore failed children and synthesize partial results. A failed child means the task is incomplete
- **INFO-041** [Parent–Child Contract](parent-child-contract.md) — The parent provides: (why it matters — the child's decision criterion), (the desired final condition — this is the acceptance criteria), (task boundar…
- **INFO-042** [Streaming Delegation (opt-in)](streaming.md) — By default delegation is all-or-nothing: a parent that delegates several children blocks until every child settles (the batch gather), so it cannot ac…
- **INFO-043** [Why Recursive Decomposition Works](why-it-works.md) — A delegation costs 3K tokens overhead. Doing it yourself for 3+ turns at 2K+ tokens/turn is both more expensive and lower quality
- **INFO-044** [The Mandatory Workflow](workflow.md) — Every agent except a leaf follows
<!-- pb:index:end -->
