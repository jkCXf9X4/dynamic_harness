---
title: "G2 — Delegation-boundary heal misses prose-completed children"
category: meta
summary: >
  P0 (resolved): the delegate boundary healed only on failure, so a child that
  completed in prose with no deliverable was never recovered.
parent: "README.md"
---

# G2. Delegation-boundary heal misses prose-completed children

**Severity:** P0 — breaks a core promise. **Status:** RESOLVED.

**Concept promise:** self-healing Layer 1 "resume-once" is for *"terminated
without a normal report, or terminated with a report but produced no
deliverable"* — the prose-answer failure mode is the motivating example
(`self-healing.md:86-88`).

**Implementation (before):** at the **root** boundary `_recover` checks the
deliverable (`runtime.py:347`). At the **delegate** boundary, `_recover` was only
invoked when `child.last_failure is not None` (`agent.py:735-737`,
`agent.py:827-829`). A child that completed in prose (status `completed`, no
artifact, no `files_written`) was **not** healed there — the parent received a
"completed" result with nothing to verify, exactly the failure the concept says
should be caught.

**Breaks:** any delegation where a child answers in prose; e.g. the optimizer
generation-agent flake that motivated the design, `documentation-and-knowledge`
(an agent writes prose instead of the doc file).

**Fix direction:** at the delegate boundary, run `_recover` on any child whose
outcome is a report without a deliverable (`last_failure is None` AND
`not _has_deliverable(child)`), matching the root check.

**Status:** RESOLVED — both delegate boundaries (`agent.py`
`_gather_deferred_and_finalize` and `run_delegate_tool`) now heal on
`not _has_deliverable(child)` instead of `child.last_failure is not None`, so a
prose-completed child is recovered exactly like at the root.
