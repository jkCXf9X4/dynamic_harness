---
id: INFO-080
type: info
title: G2 — Delegation-boundary heal misses prose-completed children
summary: P0 (resolved): the delegate boundary heals on a missing deliverable, so a prose-completed child is recovered.
date: 2026-09-23
status: current
---

# G2 — Delegation-boundary heal misses prose-completed children

**Severity:** P0. **Status:** resolved.

**Current state:** both delegate boundaries (`agent.py`
`_gather_deferred_and_finalize` and `run_delegate_tool`) heal on
`not _has_deliverable(child)`, not on `child.last_failure is not None`. A
child that completed in prose with no deliverable is recovered exactly like at
the root boundary.

## Owns
- G2 gap outcome: the delegate boundary heals prose-completed children.

## Excludes
- Self-heal design: `02-architecture/concepts/self-healing/`.
