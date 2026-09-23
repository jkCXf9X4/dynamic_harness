---
title: "G1 — VERIFY is prompt discipline, not a mechanism"
category: meta
summary: >
  P0: the mandatory VERIFY step and plan acceptance criteria are never
  mechanically checked; blind synthesis is undetectable.
parent: "README.md"
---

# G1. VERIFY is prompt discipline, not a mechanism; acceptance criteria are never checked

**Severity:** P0 — breaks a core promise. **Status:** open.

**Concept promise:** the mandatory `ANALYZE → DECOMPOSE → DELEGATE → VERIFY →
SYNTHESIZE` loop (VISION), success criterion #1 "every sub-agent's output
verified (artifact read, content confirmed)", and `plan`'s *acceptance criteria*
are meant to gate termination.

**Implementation:** the only mechanical check is `_has_deliverable`
(`runtime.py:261-273`) — file *existence*, not content or correctness. The `plan`
tool records `acceptance` into the `FocusLedger` (`tools/planning.py:25-35`,
`agent.py:220-242`), but **nothing ever evaluates them**. Blind synthesis
(anti-patterns AP-3/AP-7) is undetectable by the runtime; "done" is whatever the
agent's `report()` declares.

**Breaks:** every use-case that relies on "verify before synthesize" as a
guarantee — most directly `../../01-product/use-cases/repository-analysis.md`
§Verification, and the whole evaluation-and-qa family (which currently works only
because the *benchmark* adds its own verifier).

**Fix direction:** a report-time acceptance check — e.g. the parent's
`read_artifact` + a mechanical "does the artifact mention the acceptance terms /
does it exist and is non-empty" gate on children that declared
`plan(acceptance=...)`, plus a runtime flag `verify_children=true` that
re-delegates or escalates a child whose acceptance criteria are unmet.
