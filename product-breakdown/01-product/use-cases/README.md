---
title: "Use-Cases — Index"
category: use-case
summary: >
  Deduced taxonomy of plausible use-cases for Dynamic Harness, grounded in the
  concepts and the actual tools/runtime. Each family links to the capabilities
  it relies on; the fitness filter decides whether a task belongs here at all.
related:
  - ../../02-architecture/concepts/delegation-model/README.md
  - ../../02-architecture/concepts/artifact-system/README.md
  - ../../02-architecture/concepts/agent-lifecycle/README.md
  - ../../02-architecture/concepts/self-healing/README.md
  - ../../00-intent/VISION.md
  - ../../05-operation/guides/programmatic-usage/README.md
  - ../requirements/README.md
---

# Use-Cases

Deduces **plausible use-cases** for Dynamic Harness from the concepts
(`../../02-architecture/concepts/`) and the concrete runtime/tools in `src/`.
Use-cases sit between a user's real-world goal and the framework's mechanics —
they answer *"what would someone actually use this for?"*.

Before adding a family, apply the [fitness filter](fitness-filter.md); for the
shared decomposition model and tool vocabulary behind every family, see
[mapping and tools](mapping-and-tools.md).

## Owns
- The use-case taxonomy and the fitness criteria for membership
- The common mapping from use-case → architecture and tool vocabulary

## Excludes
- Capabilities, scope, acceptance → `../README.md`, `../requirements/`
- Organizing design → `../../02-architecture/`
- Test mechanics → `../../04-verification/`

## Use-Case Families

| Family | What class of work | Archetype tool flow |
|---|---|---|
| [Repository analysis](repository-analysis.md) | Inventory, audit, security, TODO/debt, structure | `glob`/`grep`/`read` → parallel role-scoped delegates → synthesize |
| [Change & validation](change-and-validation.md) | Bug fix, tests, refactor, small codegen | `read`/`edit`/`write` → `bash` to verify → report |
| [Documentation & knowledge](documentation-and-knowledge.md) | Generate docs, doc API surface, curate a reference library | `glob`/`read` → summarize → `write` artifact |
| [Research & synthesis](research-and-synthesis.md) | External research, comparison, source-aggregation | `webfetch` (parallel delegates) → synthesize artifact |
| [Pipelines & jobs](pipelines-and-jobs.md) | Batch extraction/transformation, long resumable jobs | `bash`/`write` per item → `prune`/`restore` → checkpoint/resume |
| [Evaluation & QA](evaluation-and-qa.md) | Benchmark suite, prompt A/B, failure triage | deterministic verifiers, fresh-Runtime runs |
| [Embedding & integration](embedding-and-integration.md) | Library use, custom agents/tools, product workflows | `Harness`/`Runtime` API + custom registry |
