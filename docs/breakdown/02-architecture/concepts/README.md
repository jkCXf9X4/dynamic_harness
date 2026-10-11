---
title: Architecture Concepts
summary: The load-bearing model concepts. Each is a folder of single-concern leaves
---

# Architecture Concepts

The load-bearing model concepts. Each is a folder of single-concern leaves.

| Concept | Covers |
|---|---|
| [Agent lifecycle](agent-lifecycle/README.md) | States, creation, run loop, termination, safety invariants |
| [Delegation model](delegation-model/README.md) | Parent/child contract, workflow, streaming, context health |
| [Artifact system](artifact-system/README.md) | Progressive disclosure, storage, commits, design principles |
| [Self-healing](self-healing/README.md) | Blunt-vs-rot, layered policy, resume/parent-heal/fresh-worker |

## Owns
- The definitions of the runtime's core model concepts

## Excludes
- Methodology that governs agents to `../methodology/`
- Multi-agent coordination design to `06-evolution/investigations/multi-agent-coordination/` (INFO-148)

## Contents

<!-- pb:index:start -->
<!-- GENERATED FILE — do not edit. Regenerate with pb-registers. -->
- [Agent Lifecycle](agent-lifecycle/README.md) — The complete lifecycle of an agent: task states, the tool-calling loop, safety invariants, termination paths, and the Agent/Runtime split
- [Artifact System](artifact-system/README.md) — Artifacts are the primary communication mechanism between agents: findings written to disk as immutable artifacts, read progressively by parents
- [Delegation Model](delegation-model/README.md) — Recursive task decomposition: parents break work into independent sub-tasks, delegate to children, verify results, and synthesize a combined output
- [Self-Healing Agents](self-healing/README.md) — How the runtime recovers an agent run that did not produce its deliverable without restarting the task — salvaging healthy work, never grinding a poisoned context
<!-- pb:index:end -->
