# Decision Records (ADRs)

Architecture decision records. One row per decision; the [decision log](../../decision-log.md)
holds the cross-layer view. Status ∈ `Proposed | Accepted | Superseded | Rejected | Deprecated`.

| ADR | Decision |
|---|---|
| [AD-001](AD-001.md) | Reject parent-mediated relaying for collaboration |
| [AD-002](AD-002.md) | Collaboration group = children of a common parent, explicit membership, default-deny |
| [AD-003](AD-003.md) | Collaboration channel = workspace-primary, messages-as-exception |
| [AD-004](AD-004.md) | Facilitation = mechanical policy layer + sparse parent arbitration, no facilitator agent |
| [AD-005](AD-005.md) | Founding boundary-scoped, participation universal |
| [AD-006](AD-006.md) | Spine = runtime `_links` + reuse of converse/`_inject_queue` + pointers; spec demoted |
| [AD-007](AD-007.md) | Plugin direction = interface economy (~7 seams), no loader / late injection |
| [AD-008](AD-008.md) | Comms layer = swappable routing backend behind one uniform tool surface |
| [AD-009](AD-009.md) | Node model — budgeted, navigational definition state |
