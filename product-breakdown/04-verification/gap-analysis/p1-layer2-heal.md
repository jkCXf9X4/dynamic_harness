---
title: "G7 — Self-heal Layer 2 is not a distinct mechanism"
category: meta
summary: >
  P1 (partial): the parent boundary reuses the root's shared _recover, so the
  documented separate Layer 2 tier is a naming question, not a mechanism.
parent: "README.md"
---

# G7. Self-heal Layer 2 is not a distinct mechanism

**Severity:** P1. **Status:** partially resolved via G2; naming question remains.

**Concept:** `../../02-architecture/concepts/self-healing.md:56-58` describes
Layer 2 — "parent `converse()` / resumes the child with the failure reason" — as
a separate policy tier from Layer 1.

**Implementation:** the parent boundary reuses the same `_recover`
(`agent.py:735-737`) as the root boundary; there is no parent-side diagnosis and
no separate converse-based heal. Combined with G2, the *failure* case was handled
but the *prose-completion* case (which Layer 1 is explicitly about) was not.

**Breaks:** the layered policy as documented; makes "Layer 1 → miss → Layer 3"
untestable at the delegation boundary.

**Fix direction:** either document that Layer 2 = Layer 1 applied at the parent
boundary, or implement a distinct parent-side diagnosis + `converse` heal path,
and fix the G2 deliverable check.

**Status (G2 done):** the G2 deliverable check is fixed (see
[G2](p0-delegate-heal.md)); the parent boundary now heals prose-completions too.
Whether this counts as a distinct "Layer 2" is a naming question — the mechanism
is the shared `_recover`.
