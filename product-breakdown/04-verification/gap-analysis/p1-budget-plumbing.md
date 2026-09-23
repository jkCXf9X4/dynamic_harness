---
title: "G8 — Budgeting / cost-control is dead plumbing"
category: meta
summary: >
  P1 (open): BudgetRequest plumbing exists but no tool exposes it and no spend
  cap is enforced, so a run cannot be budgeted or stopped at a token ceiling.
parent: "README.md"
---

# G8. Budgeting / cost-control is dead plumbing

**Severity:** P1. **Status:** open.

**Concept:** VISION is built on "minimize cost"; the `ask`/`escalate` model
implies an agent can request more budget (`BudgetRequest`).

**Implementation:** `request_more_budget` (`agent.py:835-842`),
`deliver_budget_request` (`runtime.py:473-474`) and the `on_budget_request`
handler all exist, but **no tool exposes them to the loop** and there is no spend
cap or enforcement anywhere. An agent cannot request a budget increase, and a run
cannot be stopped at a token ceiling.

**Breaks:** any cost-sensitive production use (the stated #1 motivation of the
project); `embedding-and-integration` (a consumer cannot set a budget).

**Fix direction:** a `request_budget` tool wired to an interactive handler +
configurable hard cap that force-fails or escalates past it.
