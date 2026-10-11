---
title: "Use-Cases — Index"
summary: >
  Deduced taxonomy of plausible use-cases for Dynamic Harness, grounded in the
  concepts and the actual tools/runtime. Each family links to the capabilities
  it relies on; the fitness filter decides whether a task belongs here at all.
---

# Use-Cases — Index

Deduces **plausible use-cases** for Dynamic Harness from the concepts in
`02-architecture/concepts/` and the concrete runtime/tools in `src/`.
Use-cases sit between a user's real-world goal and the framework's mechanics —
they answer *"what would someone actually use this for?"*.

Before adding a family, apply the [fitness filter](fitness-filter.md); for the
shared decomposition model and tool vocabulary behind every family, see
[mapping and tools](mapping-and-tools.md).

## Owns
- The use-case taxonomy and the fitness criteria for membership
- The common mapping from use-case to architecture and tool vocabulary

## Excludes
- Capabilities, scope, acceptance — the layer index and `requirements/`
- Organizing design — `02-architecture/`
- Test mechanics — `04-verification/`

## Contents

<!-- pb:index:start -->
<!-- GENERATED FILE — do not edit. Regenerate with pb-registers. -->
- **INFO-020** [Change & Validation](change-and-validation.md) — Work that modifies a codebase and must be proven correct: bug fixes with verification, test-authoring for coverage, cross-cutting refactors, and small self-contained code generation.
- **INFO-021** [Documentation & Knowledge](documentation-and-knowledge.md) — Generate or refresh documentation from a codebase, map an API surface, and curate a durable reference library — read, summarize, write flows and progressive disclosure, with the reference library as content not scaffolding.
- **INFO-022** [Embedding & Integration](embedding-and-integration.md) — Dynamic Harness as a library inside a product or pipeline: the Harness / Runtime API, custom agent classes, custom tools, and event-handler wiring.
- **INFO-023** [Evaluation & QA](evaluation-and-qa.md) — Dogfooding the runtime as its own QA lab: run the deterministic benchmark suite, A/B-test system prompts, triage failures, and audit provenance — a first-class use-case thanks to the failable verifiers.
- **INFO-024** [Use-Case Fitness Filter](fitness-filter.md) — Not everything is a good Dynamic Harness use-case. The framework is not a chatbot, not a shared-memory assistant, and not a code-generation platform.…
- **INFO-025** [Mapping a Use-Case to the Architecture](mapping-and-tools.md) — Every use-case family is built from the same load-bearing concepts
- **INFO-026** [Pipelines & Long Jobs](pipelines-and-jobs.md) — Batch extraction/transformation over many files, and long multi-step jobs: the manyfiles pattern (one item at a time, write each result), prune/restore, and checkpoint/resume that makes an interrupted overnight job recoverable.
- **INFO-027** [Repository Analysis](repository-analysis.md) — Inventory, audit, and understand an existing codebase: security review, code quality, TODO/debt inventory, structure mapping. The canonical read-heavy family — discovery, parallel delegation, progressive disclosure, read-only.
- **INFO-028** [Research & Synthesis](research-and-synthesis.md) — Gather external information and synthesize it into a durable, source-cited artifact: competitive research, feature/API documentation, and comparison write-ups. Exercises `webfetch` and parallel sub-agents, with careful discipline around the fetcher's restrictions and the "summary is a preview, the artifact is the truth" rule.
<!-- pb:index:end -->
