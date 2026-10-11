---
title: Artifact System
summary: Artifacts are the primary communication mechanism between agents: findings written to disk as immutable artifacts, read progressively by parents
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
- Delegation orchestration to [delegation-model/](../delegation-model/README.md)
- Agent lifecycle to [agent-lifecycle/](../agent-lifecycle/README.md)
- Commit/persistence internals to `../../../../docs/api/repository.md`

See `../../../../docs/api/artifacts.md`.

## Contents

<!-- pb:index:start -->
<!-- GENERATED FILE — do not edit. Regenerate with pb-registers. -->
- **INFO-034** [Relationship to Commits](commits.md) — Every artifact is linked to a commit in the Repository
- **INFO-035** [Design Principles](design-principles.md) — Write to disk, not memory — state is durable, not ephemeral
- **INFO-036** [Progressive Disclosure](progressive-disclosure.md) — Artifacts expose six detail levels, headline to raw data, so a parent reads a short preview and loads deeper detail only on demand
- **INFO-037** [Immutability, Storage & Access](storage.md) — Artifacts are write-once and immutable: once an agent calls `report()`, the Runtime creates the artifact, ensuring reproducibility, traceability, and safety
<!-- pb:index:end -->
