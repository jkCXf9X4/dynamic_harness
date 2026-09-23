# Requirements — Steering, Safety, Commons (REQ-8..15)

Continued from [requirements-group.md](requirements-group.md). Theory behind each
requirement in brackets.

## Steering and safety (parent = broker, not content reader)
- **REQ-8 Risk-point coaching only.** The parent is awakened only for: new
  connection, over-budget exchange, escalation, or a child lacking context (the
  Netflix "step in" list). It does not check in between.
  [Hackman: periodic coaching; Netflix: step in at risk points]
- **REQ-9 Loop detection.** Per-pair exchange counter + settle-then-yield;
  breach → close channel + notify parent. Scoped to the group edge set (small,
  known to the runtime). [repeated-call detection generalization]
- **REQ-10 Lifecycle.** Channels close when the parent settles or is killed;
  settled siblings are read-only targets (no messaging). Cost of a bad hookup
  (mis-connection, ghosting) is one wasted message.
  [transaction costs — cheap failures]
- **REQ-11 Dissent is engineered.** Seed at least one independent or contrarian
  link per material group (a verifier, or a cross-scope child), and periodically
  connect *non-overlapping* siblings to bring novel input — the systemic antidote
  to group-think. [cognitive diversity; Granovetter weak ties; farming for dissent]
- **REQ-12 Child autonomy is protected.** An incoming sibling message is
  advisory, not authoritative; a child may ignore it, challenge it, or escalate
  to the parent. Failure to speak up (hiding bad news) must never be cheaper than
  surfacing it. [psychological safety; Edmondson: failure framing is informational]

## Commons governance (from the facilitation-layer analysis, Ostrom)
- **REQ-13 Graduated sanctions, not instant failure.** Violations of
  channel/workspace rules follow a ladder: warn → tighten (reduce cap) → hard
  stop → notify parent. Proportional, observable, reversible. [Ostrom principle 5]
- **REQ-14 Conflict-resolution arena.** Disputes resolve at the lowest cost:
  child↔child negotiation on the rich channel first; if unresolved, a single
  escalation to the parent arbitrates once (arbitrate / converse / disconnect /
  dissolve group). Resolution is recorded to provenance.
  [Ostrom principle 6 — "rapid access to low-cost local arenas"]
- **REQ-15 Monitoring is distributed, not appointed.** Workspace writes are
  append-only and committed (provenance), so any group member can audit any
  other's contributions at near-zero cost. No dedicated monitor agent.
  [Ostrom principle 4 — "monitors are the users"]
