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
