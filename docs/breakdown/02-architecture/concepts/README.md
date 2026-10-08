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
- Methodology that governs agents → `../methodology/`
- Multi-agent coordination design → `../multi-agent-coordination/`

## Contents

<!-- pb:index:start -->
<!-- GENERATED FILE — do not edit. Regenerate with pb-registers. -->
- [Agent Lifecycle](agent-lifecycle/README.md) — The complete lifecycle of an agent — from creation through execution to termination: task states, the tool-calling loop, safety invariants, terminatio…
- [Artifact System](artifact-system/README.md) — Artifacts are the primary communication mechanism between agents: instead of passing raw context between parent and child, agents write findings to di…
- [Delegation Model](delegation-model/README.md) — Recursive task decomposition: parent agents break work into independent sub-tasks, delegate to child agents, verify results, and synthesize a combined…
- [Self-Healing Agents](self-healing/README.md) — How the runtime recovers an agent run that did not produce its intended deliverable without restarting the whole task — salvaging healthy work while n…
<!-- pb:index:end -->
