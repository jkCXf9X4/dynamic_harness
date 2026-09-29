---
title: Artifact System
summary: "Artifacts are the primary communication mechanism between agents: instead of passing raw context between parent and child, agents write findings to di…"
---

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

See `../../../../docs/api/artifacts.md`.

## Contents

<!-- pb:index:start -->
- **INFO-034** [Relationship to Commits](commits.md) — Every artifact is linked to a commit in the Repository
- **INFO-035** [Design Principles](design-principles.md) — Write to disk, not memory — state is durable, not ephemeral
- **INFO-036** [Progressive Disclosure](progressive-disclosure.md) — In a naive agent framework, a child agent might return 30,000 tokens of raw findings to its parent. The parent's context window fills with data it may…
- **INFO-037** [Immutability, Storage & Access](storage.md) — Artifacts are write-once, never modified. Once an agent calls , the Runtime creates the artifact and it becomes immutable. This ensures
<!-- pb:index:end -->
