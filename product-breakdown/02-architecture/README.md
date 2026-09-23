# Layer 02 — Architecture

**How are deliverables, evidence, and work organized?**

The architecture is the ISO/IEC 15288 systems-engineering shape applied to agent runs: every task is a system broken into system elements (sub-agents) via ANALYZE → DECOMPOSE → DELEGATE → VERIFY → SYNTHESIZE → TERMINATE, with requirements flowing down and verification flowing up (V-model). The organizing principles are fresh-context economics, actor-model isolation (know only parent/children/task), artifact-driven communication with progressive disclosure, and git-like provenance. This layer holds the *organizing design* — the methodology that governs all agents, the concepts that define the model, the collaboration design (multi-agent coordination), worked examples, and the decision records (ADRs) that lock architecture choices.

## Owns
- Structure, components, data flow, integration, quality attributes
- Methodology/guidelines governing how agents decompose, delegate, verify, synthesize
- Concepts (delegation model, artifact system, agent lifecycle, self-healing)
- Multi-agent coordination design (topology decision, collaboration spec)
- Decision records (ADRs) for this and cross-cutting layers

## Excludes
- Script interfaces, file notes, test cases → `03-implementation/`, `04-verification/`
- Release steps → `05-operation/`
- Scope/capabilities → `01-product/`
- Future features → `06-evolution/`

## Contents

- [methodology/](methodology/README.md) — mandatory workflow, golden delegation rule, priorities, verification, anti-patterns (P0–P6)
- [concepts/](concepts/README.md) — [delegation-model](concepts/delegation-model/README.md), [artifact-system](concepts/artifact-system/README.md), [agent-lifecycle](concepts/agent-lifecycle/README.md), [self-healing](concepts/self-healing/README.md)
- [examples/](examples/README.md) — worked execution patterns
- [decisions/](decisions/README.md) — ADR decision records (AD-001…AD-009; see `product-breakdown/decision-log.md`)
- [multi-agent-coordination/](multi-agent-coordination/README.md) — topology design space (REQ-1…15), [collaboration setting](multi-agent-coordination/collaboration-setting/README.md), [management theory](multi-agent-coordination/management-theory/README.md)

The strongest rationale artifacts in this layer — the multi-agent INVESTIGATION and the verifier's evidence chain in `04-verification/` — are preserved as-is; the layer structure *wraps* them, it does not replace them.