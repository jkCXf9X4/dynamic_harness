---
title: Multi-Agent Coordination
summary: Design space for peer collaboration between sibling agents. Entry point is `INFO-148` (canonical record + open questions); conclusions are the canonical leaves.
---

# Multi-Agent Coordination

Design space for peer collaboration between sibling agents. Entry point is
`INFO-148` (canonical record + `INFO-171` open questions); conclusions are the
canonical leaves.

## Chain status
- **Question** — present, in `INFO-148` + `INFO-171`.
- **Plan** — present, in `INFO-175` + the collaboration-setting index.
- **Findings** — PENDING. The management-theory index is a survey, not findings.
- **Results** — PENDING.

| Area | Leaves |
|---|---|
| Design space | [scope-options](scope-options.md), [sibling-collaboration](sibling-collaboration.md), [sibling-scoping](sibling-scoping.md), [spine](spine.md), [capability-scope](capability-scope.md), [collaboration-setting-model](collaboration-setting-model.md) |
| Requirements | [requirements-group](requirements-group.md) (REQ-1..7), [requirements-steering](requirements-steering.md) (REQ-8..15) |
| Introduce, not mediate | [introduce-not-mediate](introduce-not-mediate.md), [introduce-risks](introduce-risks.md) |
| Channel | [channel-decision](channel-decision.md), [channel-evidence](channel-evidence.md) |
| Facilitation & governance | [facilitation-layer](facilitation-layer.md), [ostrom-principles](ostrom-principles.md) |
| Collaboration setting spec | [collaboration-setting/](collaboration-setting/README.md) (REQ-1..15, AC-1..11) |
| Management theory | [management-theory/](management-theory/README.md) (leadership, mechanisms, playbook) |

## Contents

<!-- pb:index:start -->
<!-- GENERATED FILE — do not edit. Regenerate with pb-registers. -->
- [Collaboration Setting (Team) — Advanced Layer Spec](collaboration-setting/README.md) — Behavioral spec for the advanced collaboration layer. The core spine is simpler: runtime `_links` (authorized peer pairs) + reuse of existing converse/_inject_queue delivery + artifact/result pointers. Team-object features are policy layers on that spine.
- **INFO-148** [Direction: Complicated to Complex Multi-Agent Coordination](INVESTIGATION.md) — Direction work (pre-implementation) for moving from parallel decomposition to multi-agent coordination, where a parent stands up children that communicate and solve together. Option A (parent relaying) is rejected — see `AD-001`.
- **INFO-149** [Capability Scope: Founding Boundary-Scoped, Participation Universal](capability-scope.md) — Is child collaboration an orchestration feature or a general capability? Answer: founding is parent-scoped (any node with children), participation is universal (every agent, leaves included).
- **INFO-150** [Channel Decision: Workspace-Primary, Messages-as-Exception](channel-decision.md) — The collaboration channel is a shared, scoped workspace as the primary substrate; peer messages are the scarce, bounded exception, used only for equivocal coordination.
- **INFO-151** [Channel Evidence: Why Workspace-Primary](channel-evidence.md) — The theory anchors behind the channel decision. The decision itself is in `INFO-150`; decisions: `AD-003`
- **INFO-159** [Collaboration Setting = Hackman's Conditions per Layer](collaboration-setting-model.md) — A concrete collaboration-setting object (a team workspace opened by the founding parent) maps 1:1 onto Hackman's five conditions; the first two are the non-negotiable core.
- **INFO-160** [Facilitation Layer: Facilitation Yes, Facilitator Agent No](facilitation-layer.md) — Should the channel have a facilitator or stay pure child-to-child? Theory resolves it as a three-layer stack: L0 pure peering, L1 mechanical policy, L2 sparse parent arbitration. No facilitator agent.
- **INFO-161** [Parent Role: Introduce, Don't Mediate](introduce-not-mediate.md) — Should the parent inject child IDs (introduce siblings) without overseeing the exchanges? Verdict: yes, this is the right shape of B, and close to fully supported by existing plumbing.
- **INFO-162** [Introduce: Risks, Cons, and the B-vs-C Picture](introduce-risks.md) — Honest risks of the introduce model and how it changes the B-vs-C decision. Decisions: AD-002, AD-003
- **INFO-171** [Open Questions (before implementation)](open-questions.md) — The questions the investigation must resolve before the multi-agent coordination design is implemented. Record: INVESTIGATION.md
- **INFO-172** [Ostrom's Commons Governance (Evidence for Facilitation)](ostrom-principles.md) — Elinor Ostrom's analysis of long-lived shared-resource groups is the direct analogue of a shared artifact workspace: sustainable self-governance is neither anarchy nor a boss, but explicit institutional design (mechanisms, not a person).
- **INFO-173** [Requirements — Group, Context, Norms (REQ-1..7)](requirements-group.md) — Consolidated guardrails from the B-curated deep-dive, strengthened by the 8 design implications from the management-theory report. REQ-1..7: group, context, norms.
- **INFO-174** [Requirements — Steering, Safety, Commons (REQ-8..15)](requirements-steering.md) — Continued from `INFO-173`. Theory behind each requirement in brackets
- **INFO-175** [Collaboration Scope Options (A/B/C)](scope-options.md) — Three candidate scopes for moving from complicated decomposition to complex coordination. A (parent relays) is REJECTED; work continues on B (siblings message) and C (bounded shared workspace with a chair).
- **INFO-176** [Sibling Collaboration (B-curated): Common-Parent Scoping](sibling-collaboration.md) — How to enable real collaboration (B) while containing its cons: constrain peer-to-peer communication to siblings that share a common parent (children of one parent form a team).
- **INFO-177** [Sibling Scoping: Mitigations and Residual Concerns](sibling-scoping.md) — How common-parent scoping mitigates each of option B's cons, and what it does not fix. Decisions: AD-002
- **INFO-178** [Simplicity Review: The Spine — Links + Delivery + Pointers](spine.md) — The collaboration-setting spec over-modeled. The advanced features (team object, charter, norms, sanctions, workspace, arbitration ladder) are policy layers on a much smaller spine of three primitives, mostly existing machinery.
- [Management Theory — Communication & Facilitation](management-theory/README.md) — The theory survey behind the multi-agent coordination design (parent introduces siblings, children collaborate directly). Every theory is followed by a design translation onto the agent runtime.
<!-- pb:index:end -->
