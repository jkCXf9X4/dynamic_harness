---
title: Layer 01 — Product
summary: What is delivered, out of scope?
---

# Layer 01 — Product

The product is a recursive agent runtime with artifact-based communication, strict context encapsulation, and Git-like provenance. The CLI requirements doc below is the CLI sub-spec and belongs here because it defines the delivered terminal surface.

## Product Definition

### Capabilities (from README.md / AGENTS.md)
- **Recursive decomposition** — parent agents decompose work and delegate to focused sub-agents with fresh, isolated contexts; parent orchestrates, children implement.
- **Deterministic safety machinery** — repeated-call detection, fuzzy near-identical `bash` detection, opaque result handles (`result_read`/`result_bash`), spawn caps per-lineage, checkpoint resume — enforced in code, not prompt advice.
- **Blunt-vs-rot self-healing** — resume-once for blunt stops vs fresh worker for context rot, one shared heal budget per child.
- **Artifact-driven communication + progressive disclosure** — findings to disk as immutable artifacts; parents consume summaries (~300 tokens), detail loaded lazily.
- **Git-like provenance** — every completed task creates a Commit with parent/child links; runs are auditable and resumable.
- **Actor-model isolation** — agents know only parent, children, and task.
- **CLI + embedding** — minimal prompt-only terminal with always-available input; `Harness` programmatic API; 25 extensible tools; failable benchmark verifiers + prompt optimizer.

### Out of Scope (VISION "What This Is NOT")
- Not a chatbot framework — conversations are not state
- Not a predefined workflow engine — agents decide decomposition dynamically
- Not a code generation platform — agents use tool calls, not generated code
- Not a shared-memory system — no global context, no element registry accessible to workers

### Acceptance Criteria (VISION success criteria)
1. Every sub-agent's output **verified** (artifact read, content confirmed)
2. Synthesis accurately reflects artifact contents (no fabrication)
3. No failed child abandoned — all failures retried or escalated
4. Total context across all agents remains shallow
5. Cost proportional to task complexity, not context duration

Criterion 1 (verification) is open gap `INFO-081`.

## Owns
- Scope, capabilities, out-of-scope, acceptance expectations
- Use cases and requirements (the CLI sub-spec below)
- Product-level glossary

## Excludes
- Organization, architecture, components, data flow to `02-architecture/`
- Implementation details, scripts, configs to `03-implementation/`
- Test mechanics, proof, gap analysis to `04-verification/`
- Runbooks, release steps to `05-operation/`
- Roadmap, backlog to `06-evolution/`

## Contents

<!-- pb:index:start -->
<!-- GENERATED FILE — do not edit. Regenerate with pb-registers. -->
- [Requirements — CLI Sub-Spec (Index)](requirements/README.md) — Requirements governing the delivered terminal surface and the persisted overview (retired DL-12; read via `pb archive read deprecated/decision-log.md`); the runtime's product definition lives in the layer index.
- [Use-Cases — Index](use-cases/README.md) — Deduced taxonomy of plausible use-cases for Dynamic Harness, grounded in the concepts and the actual tools/runtime. Each family links to the capabilities it relies on; the fitness filter decides whether a task belongs here at all.
<!-- pb:index:end -->
