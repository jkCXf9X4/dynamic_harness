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

- [agent_methodology_guidelines.md](agent_methodology_guidelines.md) — mandatory workflow, golden delegation rule, anti-patterns (P0–P6)
- [concepts/](concepts/) — delegation-model, artifact-system, agent-lifecycle, self-healing
- [examples/](examples/) — worked execution patterns
- [decisions/](decisions/) — ADR decision records (created in a parallel track; see `product-breakdown/decision-log.md`)
- [multi-agent-coordination/](multi-agent-coordination/) — INVESTIGATION.md (topology design space, REQ-1…15), collaboration-setting-spec.md, management-theory-communication-facilitation.md

The strongest rationale artifacts in this layer — the multi-agent INVESTIGATION and the verifier's evidence chain in `04-verification/` — are preserved as-is; the layer structure *wraps* them, it does not replace them.