# Channel Evidence: Why Workspace-Primary

The theory anchors behind the channel decision. The decision itself is in
[channel-decision.md](channel-decision.md); decisions:
[AD-003](../decisions/AD-003.md).

## 1. Media Richness Theory (Daft & Lengel, 1986)
The sharpest fit. Richness is the medium's ability to "change understanding
within a time interval." Managers match **medium richness to message
equivocality**: *equivocal* coordination (ambiguity, conflicting
interpretations, negotiation, "why is this wrong?") needs **rich** media (fast
feedback, personal focus ≈ direct messages); *uncertain* coordination (a value, a
finding, a file that already exists) needs only **lean** media (written,
asynchronous, reusable ≈ shared workspace / artifacts). Big-cheat version:
**pass information through the workspace; negotiate meaning through messages.**
Too-lean media for equivocal tasks causes more difficulties than too-rich media
for lean tasks — so when in doubt, the workspace (lean) is safe only for
non-equivocal exchange.

## 2. Boundary objects (Star & Griesemer, 1989)
The workspace artifact *is* the classic collaboration medium. Boundary objects
"allow coordination without consensus": plastic enough for each party's local
needs, robust enough to keep a common identity. The same shared artifact
coordinates specialists who never need to agree on interpretation — precisely
the cross-role child case. Direct negotiation between specialists is a *worse*
path: the boundary-objects literature (Kertcher & Coslor) found pre-stabilization
periods *forcing* direct cross-boundary negotiation are "frustrating" and
escalate friction.

## 3. Blackboard / distributed AI (Hearsay-II lineage)
The canonical multi-agent pattern is specialist modules coordinating *through a
shared blackboard* and never messaging each other directly. Where the "team" is
independent specialists contributing to a joint result, the proven substrate is
a shared store, not a chat network.

## 4. Modern collaborative engineering (git / PR / code review)
Practice settled the question empirically: teams coordinate **on the artifact**
(repo, diff, PR), and messages ride *on top of* artifacts (review comments
anchored to lines) rather than replacing them. The artifact is the hub; chat is
the overlay.

## 5. Thompson's coordination mechanisms (1967)
Least-cost rule: prefer the cheapest mechanism that works (shared artifacts /
plans) and escalate to mutual adjustment (direct messages) only when the cheaper
one fails. Complementary to media richness: cost-ordered, workspace first.

## 6. Reconciling with the earlier management survey
- **TMS (Wegner)** resolves the apparent tension: the *store* is the artifact;
  the *directory* ("who knows what") and *retrieval* ("ask the right person") are
  messages — two layers, not rivals. Messages **route to** artifacts.
- **Hackman's norms** and **transaction costs** both prefer artifacts: an opaque,
  versioned, reusable artifact is cheaper per use than an interrupted recipient.
- **McChrystal's empowerment** is served by workspace transparency (shared
  dashboard), with messages as the exceptional live call.
- **Amabile/autonomy & psychological safety** are *supported*: children act on
  their own against a shared surface of truth, and can surface disagreement by
  writing, not just pinging.
