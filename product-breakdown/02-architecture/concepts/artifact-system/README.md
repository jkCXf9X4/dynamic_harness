# Artifact System

Artifacts are the primary communication mechanism between agents: instead of
passing raw context between parent and child, agents write findings to disk as
immutable artifacts. Parents read summaries first and progressively load detail
as needed.

## Owns
- The context-bloat problem and the progressive-disclosure solution
- The six view levels and how parents consume them
- Immutability, on-disk storage, programmatic access
- Relationship to commits; hierarchical summarization; design principles

## Excludes
- Delegation orchestration → [delegation-model/](../delegation-model/README.md)
- Agent lifecycle → [agent-lifecycle/](../agent-lifecycle/README.md)
- Commit/persistence internals → `../../../../docs/api/repository.md`

## Contents
- [progressive-disclosure.md](progressive-disclosure.md) — the problem, six levels, usage flow
- [storage.md](storage.md) — immutability, on-disk layout, programmatic access
- [commits.md](commits.md) — artifact↔commit linkage and provenance
- [design-principles.md](design-principles.md) — principles, why not in-memory, summarization

See `../../../../docs/api/artifacts.md`.
