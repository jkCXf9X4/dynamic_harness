# Collaboration Setting = Hackman's Conditions per Layer

A concrete "collaboration setting" object (a team workspace opened by the
founding parent) maps 1:1 onto Hackman's five conditions — the first two being
the *non-negotiable* core. Decisions: [AD-005](../decisions/AD-005.md).

## Hackman condition → realization
1. **A real team** — membership is bounded and explicit: `collaborate_with=[...]`
   is the boundary. Nobody is unclear about who is on the team. (REQ-1)
2. **A compelling direction** — a **team charter** posted as the workspace's
   first artifact: collective objective, why it matters, acceptance criteria.
   Challenging, clear, consequential. Doubles as the mechanical G1 acceptance
   target to verify team output against.
3. **Enabling structure** — team norms as the policy object (REQ-6) + per-member
   roles already set by delegation.
4. **Supportive context** — the scoped workspace + provenance + budgets the
   runtime provides (REQ-15).
5. **Expert coaching** — the parent's L2 arbitration — sparse, at
   transitions/conflicts (REQ-8, REQ-14).

Because founding is boundary-scoped, this object is **the same class at every
layer**: each parent instantiates one for its interdependent children, and a
child that is itself a parent instantiates a nested one for its own children —
"facilitate child layer-by-layer collaboration" *is* the recurrence of this
object down the tree. Directives to children and charters alone do not make a
team; the *bounded, scaffolded setting* is what Hackman #1/#2 formalize.

## Relationship to the orchestrator's existing workflow
Collaboration is an **orchestration modality at decomposition time**, not a
separate system. The orchestrator's loop gains a team-forming variant:

```
ANALYZE → DECOMPOSE → [form team IF interdependent] → DELEGATE
        → VERIFY (on the workspace) → SYNTHESIZE → TERMINATE
```

- **Independent units** → plain parallel delegation, unchanged.
- **Interdependent units** → the parent *founds a team* among them (context, not
  control): declare membership, post the charter, open the workspace, introduce.
  Then it *stays out* of the steady state — the children coordinate in the
  workspace; the parent's VERIFY checks workspace output against the charter's
  acceptance criteria (closing G1's "verify is only prompt-discipline" gap), and
  SYNTHESIZE consumes settled team artifacts.
- The parent's role in the team is the **coach-transitions-only** role
  (Hackman #5), never a relay.

So the *setting* is an orchestration output at each boundary; the *work done
inside it* is general — the leader sets conditions, the team performs.

## Codified: one distributed capability, two facets, structural activation
The capability is **one object distributed to every node**, carrying **two
facets**, where **activation is structural, not role-based**:
- **MEMBER facet** — always available; active iff a parent introduced you.
  Receive/decline an introduction; read/write the team workspace (scoped);
  bounded messages to introduced siblings; negotiate / escalate.
- **FOUNDER facet** — always available; active iff you have children. Declare
  membership (`collaborate_with` / `introduce`); post the team charter (direction
  + acceptance); open the nested team workspace; arbitrate conflicts (L2 arena).

Design consequences:
1. **No class split, no role string, nothing to promote.** A node is a *member*
   of its parent's team and, once it delegates, automatically a *founder* of its
   own nested team — the same object, both facets idle until structure activates
   them. Layer-by-layer collaboration is *compositional by construction*; deeper
   subtrees inherit the tooling with zero reconfiguration (as the runtime already
   treats leaf vs orchestrator as a per-task property of the same `Agent`).
2. **Distribution ≠ privilege.** Member writes are scoped to the team workspace
   they were introduced to; founder actions require `self.children` non-empty. A
   node with no team and no children holds the object but no active workspace.
3. **The founding decision still lives at each boundary.** Uniform machinery
   changes *where the code lives*, not *who decides membership*: membership and
   charter are still declared by the parent of that layer.
4. **Implementation shape.** One `CollaborationCapability` mixin bundled into
   `Agent` (like the tool set), backed by runtime-registered team workspaces; the
   member/founder split is enforced by the scoping policy, not agent classes.
