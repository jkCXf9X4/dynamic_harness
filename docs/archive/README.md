<!-- GENERATED FILE — do not edit. Regenerate with pb-registers. -->

# Decision Stream

Flat, dated history of every committed design choice. Current state lives
in the layer leaves named by each record's `state:` field.

Records live in the cold-storage archive; extract one with `pb archive read <ID>`.

## By Layer

### Architecture

- **AD-001** — Reject Parent-Mediated Relaying for Collaboration · accepted · 2026-09-22 · `AD-001`
  The parent introduces and oversees collaboration but never relays child-to-child content.
- **AD-002** — Collaboration Group = Children of a Common Parent, Explicit Membership, Default-Deny · accepted · 2026-09-22 · `AD-002`
  A collaboration group is children of a common parent with explicit membership, and peer messaging is default-deny.
- **AD-003** — Collaboration Channel = Workspace-Primary, Messages-as-Exception · accepted · 2026-09-22 · `AD-003`
  Collaboration runs on a shared scoped workspace as the primary channel, with peer messages as the scarce exception for equivocal coordination.
- **AD-004** — Facilitation = Mechanical Policy Layer + Sparse Parent Arbitration, No Facilitator Agent · accepted · 2026-09-22 · `AD-004`
  Facilitation is a three-layer stack of pure peer-to-peer, mechanical policy, and sparse parent arbitration, with no facilitator agent.
- **AD-005** — Founding Boundary-Scoped, Participation Universal · accepted · 2026-09-22 · `AD-005`
  Any node with children may found a team, while every agent at any depth may participate as a member.
- **AD-006** — Spine = Runtime `_links` + Reuse of Converse/_inject_queue + Artifact/Result Pointers; Spec Demoted to Advanced Policy Layer · accepted · 2026-09-22 · `AD-006`
  The collaboration core is a three-primitive spine of links, reused converse delivery, and artifact pointers, with the spec demoted to policy.
- **AD-009** — Node Model — Budgeted, Navigational Definition State · accepted · 2026-09-23 · `AD-009`
  Every breakdown markdown file is a size-budgeted node (index ≤40 lines, leaves and records ≤50, hard cap 75) enforced mechanically.

### Implementation

- **AD-007** — Plugin Direction = Interface Economy (~7 Seams), No Loader / Late Injection · accepted · 2026-09-22 · `AD-007`
  The codebase stays plugin-ready through roughly seven narrow common interfaces, with no loader, late injection, or discovery.

### Verification

- **AD-008** — Comms Layer = Swappable Routing Backend Behind One Uniform Tool Surface · accepted · 2026-09-22 · `AD-008`
  All agent communication flows through one uniform tool surface over a swappable routing backend chosen per topology.
