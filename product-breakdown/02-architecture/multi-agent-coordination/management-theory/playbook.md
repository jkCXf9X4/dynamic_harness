# Playbook: The "Introduce, Don't Mediate" Parent

Sections 6–7 of the management-theory survey. Index: [README.md](README.md).

## The parent's facilitative job has exactly four moves
1. **Set up the group (Hackman: real team).** Membership is explicit and bounded:
   "you may collaborate with: B, C" is the boundary. Nobody is "maybe on the
   team."
2. **Supply context, not approvals (Netflix).** Every connection ships *why*
   ("B is analyzing the same module; you each hold half the picture"). No message
   *content* passes through the parent.
3. **Coach at transitions only (Hackman; servant leadership).** The parent is
   present at introduction (forming), connect/disconnect (composition), and
   escalation/over-budget (recovery). Absent from routine exchanges (performing).
4. **Protect the knowledge directory (Wegner; TMS).** Prefer
   introduce-over-redelegate; keep live children in place when they hold context;
   treat the sibling map as a maintained asset, not an accident.

## Anti-patterns to defend against (each maps to a rejected design)
- Parent reads/forwards message content → relaying → option A (rejected).
- Parent "checks in" at every exchange → micromanagement tax.
- Letting the mail system address the whole runtime → unconstrained B (no real
  team, no norms, no psychological safety).
- Constantly re-delegating to fresh strangers → destroying the transactive
  memory system.

## Design implications to take into the spec
These are the *mechanical* conclusions that flow into the B-curated spec
(guardrails in [../requirements-group.md](../requirements-group.md) and
[../requirements-steering.md](../requirements-steering.md)):
1. **`introduce` ships only metadata + why**: sibling ID, one-line rationale,
   scope-norm reminder. Never a payload.
2. **Norms are policy objects, not prompt text** (mirroring
   `ToolPermissionPolicy`): delivery caps, advisory-only semantics,
   settle-then-yield, escalation-on-conflict. Hackman's "norms" made concrete.
3. **The group is a first-class scoped concept**: "children of common parent +
   explicit membership" — Project Aristotle's "don't leave membership unclear."
4. **Introductions are requestable and declinable.** A blocked child `ask`s, the
   parent routes (broker), a child can decline without friction.
5. **Risk-point coaching only.** The parent is awakened for: new connection,
   over-budget exchange, escalation, child without context. Never for routine
   peer traffic.
6. **Dissent is engineered**: seed at least one independent or contrarian link
   per material group, not rely on it emerging.
7. **Cadence substitutes for control**: settlement events are the standup; a
   "must persist before speaking" rule plays the role of rhythm without
   permission.
8. **Parent context is protected by construction** (transaction costs + bounded
   rationality): the parent's per-child visibility is summarize-only; any
   curiosity about content is pull-only (`read_artifact`).
