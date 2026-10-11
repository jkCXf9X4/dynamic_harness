---
id: INFO-081
type: info
title: G1 — VERIFY is prompt discipline, not a mechanism
summary: P0 (open, IMP-005): the mandatory VERIFY step and plan acceptance criteria are never mechanically checked.
date: 2026-09-23
status: current
---

# G1 — VERIFY is prompt discipline, not a mechanism

**Severity:** P0. **Status:** open — tracked by `IMP-005`.

**Current state:** the only mechanical check is `_has_deliverable`
(`runtime.py:261-273`) — file existence, not content or correctness. The `plan`
tool records `acceptance` into the `FocusLedger` (`tools/planning.py:25-35`,
`agent.py:220-242`), but nothing evaluates them. Blind synthesis is undetectable
by the runtime; "done" is whatever the agent's `report()` declares.

## Owns
- G1 gap state: no mechanical verification of acceptance criteria.

## Excludes
- The fix (report-time acceptance gate): `IMP-005`.
- Use-cases that rely on verify-before-synthesize: `INFO-027`, `INFO-023`.
