---
title: Layer 02 — Architecture
summary: How are deliverables, evidence, and work organized?
---

# Layer 02 — Architecture

**How are deliverables, evidence, and work organized?**

The architecture is the ISO/IEC 15288 systems-engineering shape applied to agent runs: every task is a system broken into system elements (sub-agents) via ANALYZE → DECOMPOSE → DELEGATE → VERIFY → SYNTHESIZE → TERMINATE, with requirements flowing down and verification flowing up (V-model). The organizing principles are fresh-context economics, actor-model isolation (know only parent/children/task), artifact-driven communication with progressive disclosure, and git-like provenance. This layer holds the *organizing design* — the methodology that governs all agents, the concepts that define the model, and worked examples. The collaboration design (multi-agent coordination) and its INVESTIGATION live under `06-evolution/investigations/`; the decision records (ADRs) that lock architecture choices live in the decision archive (`docs/archive/archive.zip`).

## Owns
- Structure, components, data flow, integration, quality attributes
- Methodology/guidelines governing how agents decompose, delegate, verify, synthesize
- Concepts (delegation model, artifact system, agent lifecycle, self-healing)

## Excludes
- Script interfaces, file notes, test cases → `03-implementation/`, `04-verification/`
- Release steps → `05-operation/`
- Scope/capabilities → `01-product/`
- Future features → `06-evolution/`
- Multi-agent coordination design and its investigation → `06-evolution/investigations/multi-agent-coordination/`
- Decision records → the decision archive (`docs/archive/archive.zip`, `AD-*`)

The strongest rationale artifacts from this layer — the multi-agent INVESTIGATION and the verifier's evidence chain — are preserved under `06-evolution/investigations/`; the layer structure *wraps* them, it does not replace them.

## Contents

<!-- pb:index:start -->
<!-- GENERATED FILE — do not edit. Regenerate with pb-registers. -->
- [Agent Methodology](methodology/README.md) — The guidelines governing how every agent decomposes, delegates, verifies, synthesizes, and terminates. Derived from VISION.md and the agent system pro…
- [Architecture Concepts](concepts/README.md) — The load-bearing model concepts. Each is a folder of single-concern leaves
- [Worked Examples](examples/README.md) — Concrete good-vs-bad examples that make the methodology operational
<!-- pb:index:end -->
