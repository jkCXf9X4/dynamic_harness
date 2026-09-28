# Requirements — Group, Context, Norms (REQ-1..7)

Consolidated guardrails from the B-curated deep-dive, strengthened by folding in
the 8 design implications from the management-theory report
([management-theory/playbook.md](management-theory/playbook.md)). Theory behind
each requirement in brackets. Continued:
[requirements-steering.md](requirements-steering.md).

## Group / who may collaborate
- **REQ-1 Explicit membership.** The collaboration group is a first-class scoped
  concept: "children of a common parent, plus explicit membership". Nobody is
  ambiguously on the team — a parent either introduces you or it doesn't.
  [Hackman: real team; Project Aristotle: structure & clarity]
- **REQ-2 Scope rule (default deny).** Peer messaging is denied unless the parent
  introduced the pair (delegation-time `collaborate_with=[...]` or mid-run
  `introduce(agent_a, agent_b, note)`). Enforce in `get_other_agent`/a policy
  object — the permission is an *edge*, not a global right.
  [TMS directory; bounded rationality]
- **REQ-3 Introductions are requestable and declinable.** A blocked child may
  `ask` for a pointer; the parent routes (knowledge broker). A child may decline
  an introduction with no penalty.
  [Edmondson: psychological safety; Wegner: directory lookup + route]

## Context, not content
- **REQ-4 `introduce` ships metadata + why only.** The injection carries sibling
  ID, a one-line rationale, and a scope-norm reminder. It never carries a
  payload. Content stays in artifacts. [Netflix: context over control]
- **REQ-5 Parent context is protected by construction.** The parent's per-child
  visibility is summarize-only (settlements, statuses, artifact summaries); any
  content curiosity is pull-only via `read_artifact`. The parent is never
  awakened for routine peer traffic.
  [transaction costs; bounded rationality; boundary-spanning]

## Norms as policy, not prose
- **REQ-6 Norms are policy objects, not prompt text** (mirroring
  `ToolPermissionPolicy`): per-sibling-pair message cap + per-round cap + hard
  stop, advisory-only delivery, settle-then-yield, escalation-on-conflict,
  summary-only delivery. [Hackman: enabling structure; Thompson: least-cost]
- **REQ-7 Cadence substitutes for control.** Settlement events are the "standup";
  a "persist a checkpoint/artifact before you speak again" rule gives rhythm
  without permission. [rituals over control — agile]
