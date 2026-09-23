# Capability Scope: Founding Boundary-Scoped, Participation Universal

Is child layer-by-layer collaboration an *orchestration* feature, or a *general
capability every agent possesses*? Hackman's five conditions — especially #1
(real team) and #2 (compelling direction) — are the ground. Decisions:
[AD-005](../decisions/AD-005.md).

## The answer
Split the capability along the two halves the theory already separates —
**leader sets conditions, members execute** (Hackman) and **mechanisms are
institutions, not persons** (Ostrom):
- **Founder (set up the team):** any **node with children** — at that layer.
  Acts: `collaborate_with` / `introduce`, write the charter, open the workspace,
  arbitrate. Grounding: Hackman #1/#2 are *leader-provided*; only the parent has
  the decomposition view.
- **Member (work in the team):** **every agent, at any depth**, leaves included.
  Acts: read/write the team workspace, bounded messages, negotiate, escalate.
  Grounding: Hackman #1 is about the *team*, not the level; leaves are frequently
  the interdependent parties.

## Why founding is parent-scoped, not general
- **Hackman's conditions are setup acts.** Membership (#1) and direction (#2)
  can only be declared by someone who (a) sees the whole sibling set and its
  interdependence and (b) has authority to bound it. In the actor model only the
  parent meets both — siblings never see each other until introduced
  (`agent.py:1500 get_other_agent` is the only lookup, unscoped today). A leaf
  literally cannot found a team it cannot see.
- **The TMS directory lives at the parent.** Only the parent knows "who knows
  what" across its children (Wegner); introduction is a directory-routing act.
- **Naturally layer-scoped, no role string needed.** Founding self-restricts to
  nodes that *have* children (`self.children`), cleaner than a role tag:
  collaboration scales with delegation by construction — every subtree that
  spawns interdependent children gets a team; independent fan-out needs none.
- **General founding would re-open option A/unbounded B.** For an arbitrary
  agent to introduce arbitrary others it would need global addressing and global
  authority — the exact unconstrained-B shape rejected.

## Why participation is universal (leaves included)
- **Interdependence is not depth-dependent.** Two leaf siblings each holding
  half of a result are exactly the Hackman "real team": bounded membership,
  interdependent task, shared responsibility. They must collaborate *without*
  either becoming an orchestrator.
- **It keeps trees shallow.** Leaves that can hand off via the team workspace
  stay leaves. Forcing every collaborating leaf to delegate would grow the tree
  (each handoff becomes a delegation) — against "prefer broad, flat, shallow
  trees".
- **Nested enterprises (Ostrom #8).** A node is simultaneously a *member* of its
  parent's team and, if it has children, the *founder* of its own nested team.
  Participation must be universal for the nesting to compose "layer by layer."
- **It is safe because tool-safety is scoped.** Team workspace read/write is
  scoped to the team's workspace directory; messages are bounded and
  parent-authorized. A leaf gains capability, not privilege.
