# Sibling Scoping: Mitigations and Residual Concerns

How common-parent scoping mitigates each of option B's cons, and what it does
not fix. Decisions: [AD-002](../decisions/AD-002.md).

## How common-parent scoping mitigates each of B's cons
- **Violates context encapsulation (cross-branch contamination)** — contamination
  is confined to a trusted sibling set sharing a coordinator; no global graph
  addressing, so other subtrees are never touched. Progressive disclosure: the
  recipient sees a *summary* (like a settlement), not the sender's context.
  **Mostly** mitigated — bounded + authorized, but the invariant is still
  softened for the group.
- **Needs a permission model** — scope collapses to "same parent". Default
  **denied**; enabled per-delegation (opt-in `collaborate=True` on `delegate`, or
  a parent-declared group). The parent is the existing authority — no new global
  permission system. **Strongly** mitigated.
- **Churn / looping (A↔B↔A not caught)** — cycles are bounded to a small, known
  edge set (the subtree). The runtime can track exchanges per sibling-pair and
  enforce a per-pair/per-round cap with "must settle and yield". Still new
  detection, but tiny and known. **Partially** mitigated.
- **Provenance / graph complexity** — sibling edges are internal to the parent's
  subtree; the parent remains the provenance anchor. Log exchanges as telemetry
  tagged with the common parent task_id; artifact/commit provenance unaffected.
  **Largely** mitigated.
- **Recipient inbox flood** — bounded mailbox per agent + per-sibling budget cap;
  the parent can revoke/close a channel. **Mostly** mitigated.
- **Large test surface** — restricted to parent + 2–3 children groups →
  tractable mock-LLM scenarios. **Partially** mitigated.

## Residual cons and new concerns (what scoping does NOT fix)
- **Group-internal contamination remains.** Siblings' contexts absorb each
  other's material. Mitigations: summary-only delivery, per-recipient caps, and
  the parent's final VERIFY.
- **Adverse sibling data.** One child can mislead another. Each child retains
  autonomy — a sibling message is *input*, not authority; it can ignore or
  escalate a suspicious peer to the parent.
- **When is messaging legal?** Only while the parent is active/streaming?
  Channels to a *settled* sibling should close (read its artifact instead —
  existing behavior). Define delivery vs lifecycle rules.
- **Parent visibility / load.** If the parent must read every exchange, that is
  option-A pollution again. Design: the parent is notified of *events* (channel
  opened/closed, escalation, over-budget) but not content by default; summaries
  are pull-only via `read_artifact`/`status`.
- **Is B still distinguishable from C?** With a common parent, B looks like a
  lightweight C without a mandatory chair relay. Decision point: the parent
  *relays* (A, rejected) or *oversees* (B/C)? Oversight-only keeps B's scaling
  and isolation-vs-parent properties while enabling collaboration.
