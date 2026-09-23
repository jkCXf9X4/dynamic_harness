# Introduce: Risks, Cons, and the B-vs-C Picture

Honest risks of the introduce model and how it changes the B-vs-C decision.
Decisions: [AD-002](../decisions/AD-002.md), [AD-003](../decisions/AD-003.md).

## Risks and the honest cons
- **Mis-connection.** The parent's judgment runs on summaries; it can introduce
  children whose overlap is actually a conflict. Guardrail: an introduction is an
  *invitation, not a mandate* — a child may decline, and the parent can
  disconnect. Cost of a bad hookup is tiny.
- **Group-think / echo chamber.** Siblings may reinforce a shared wrong
  direction, silently. Guardrails: keep at least one child independent of the
  group (a verifier), and the parent deliberately "farms for dissent" — connect
  *unrelated* children occasionally, sample counterevidence.
- **Ghosting.** A child ignores an introduction. Cheap — one wasted message.
- **Scope-softening, but now curated.** Isolation is still softened for the
  group, but edges are **parent-chosen**, one at a time, and revocable — not an
  open bus. Accidental cross-branch contamination drops to near zero vs
  unconstrained B.
- **Parent-load stays event-only.** If the parent later starts reading exchange
  *content* to "help", it decays back into rejected option A. Enforced by design:
  content is pull-only, and default oversight is one event line.

## What this changes in the B-vs-C picture
With introductions, B and C nearly converge: a parent-declared group with
introduced siblings *is* a lightweight panel, differing only in the exchange
model. The decision becomes:
- **B-curated** — peer *messages* are the channel (summary-only, advisory).
  Simpler, preserves per-child lifecycle/tooling.
- **C/panel** — a shared *workspace* is the channel (artifact-store dir).
  Stronger for persistent shared state, but needs write-conflict conventions the
  store doesn't enforce today.

Both keep the parent in the **enabler** seat ("context over control"); neither
requires the parent to oversee content. The channel question is resolved in
[channel-decision.md](channel-decision.md).
