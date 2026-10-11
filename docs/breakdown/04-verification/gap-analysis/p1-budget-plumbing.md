---
id: INFO-083
type: info
title: G8 — Budgeting / cost-control is dead plumbing
summary: P1 (open, IMP-008): BudgetRequest plumbing exists but no tool exposes it and no spend cap is enforced.
date: 2026-09-23
status: current
---

# G8 — Budgeting / cost-control is dead plumbing

**Severity:** P1. **Status:** open — tracked by `IMP-008`.

**Current state:** `request_more_budget` (`agent.py:835-842`),
`deliver_budget_request` (`runtime.py:473-474`) and the `on_budget_request`
handler all exist, but no tool exposes them to the loop and no spend cap or
enforcement exists anywhere. An agent cannot request a budget increase, and a
run cannot be stopped at a token ceiling.

## Owns
- G8 gap state: budgeting plumbing is inert.

## Excludes
- The fix (request-budget tool + hard token cap): `IMP-008`.
