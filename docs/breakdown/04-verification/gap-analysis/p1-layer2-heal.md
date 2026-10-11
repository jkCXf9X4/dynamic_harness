---
id: INFO-085
type: info
title: G7 — Self-heal Layer 2 is not a distinct mechanism
summary: P1 (partial, IMP-012): the parent boundary reuses the root's shared _recover; the Layer 2 naming question remains.
date: 2026-09-23
status: current
---

# G7 — Self-heal Layer 2 is not a distinct mechanism

**Severity:** P1. **Status:** partial — naming question tracked by `IMP-012`.

**Current state:** the parent boundary reuses the same `_recover`
(`agent.py:735-737`) as the root boundary; there is no parent-side diagnosis
and no separate converse-based heal. Since `INFO-080` (G2), the parent
boundary heals prose-completions too. Whether this counts as a distinct
"Layer 2" is a naming question — the mechanism is the shared `_recover`.

## Owns
- G7 gap state: Layer 2 is not a distinct mechanism.

## Excludes
- Self-heal design: `02-architecture/concepts/self-healing/`.
- The naming fix: `IMP-012`.
