# Channel Decision: Workspace-Primary, Messages-as-Exception

The collaboration channel is a shared, scoped workspace as the primary
substrate; peer messages are the scarce, bounded exception used only for
*equivocal* coordination. Decisions: [AD-003](../decisions/AD-003.md). Theory
anchors: [channel-evidence.md](channel-evidence.md).

## Decision rules
1. **To share a result, a finding, or a constraint → write/read the workspace.**
   No message needed. The artifact is the boundary object; "coordination without
   consensus" applies.
2. **To route or ask "who knows this?" → a message that points to the
   workspace** (ID + why), not a payload (mirrors REQ-4). TMS retrieval.
3. **To reconcile conflicting interpretations / demand a revision → messages**,
   the rich channel, but bounded per-pair and hard-stopped on over-budget
   (REQ-6, REQ-9) when the exchange should escalate to the parent or a fresh
   worker.
4. **Default source of truth is the workspace.** A child that read the artifact
   disagrees with a sibling's message — the artifact wins; escalate if it matters
   (REQ-12, existing VERIFY).

## Rationalisation against the criteria that rejected A
- The parent relays nothing (messages and artifacts both bypass it).
- Recipient context is protected: most coordination is *pull* (read what you
  need) rather than *push* (interruptive message) — attacking "mixed-context
  pollution" one level deeper.
- Churn/loop risk shrinks: the bounded message channel sees only equivocal
  exchanges; the workspace is naturally asynchronous and non-interruptive.

## What this does to B vs C, and what still needs investigation
This is a **hybrid** adopting C's substrate for information exchange and B's
messages for equivocal negotiation — choosing both, with a selection rule.
Residual items the theory does **not** fully decide:
- **Workspace mechanics.** A scoped directory in `ArtifactStore` needs
  write-conflict conventions and visibility rules (who may read/write what, when)
  the store does not enforce today (C's known gap). Blackboard/git practice
  (append-only + review) suggests the form; the runtime policy needs defining.
- **Cadence/round semantics.** A workspace is asynchronous; "which children are
  waiting on a sibling's write" is a new lifecycle question (settle-then-yield
  becomes "fetch newly-settled siblings once per turn" — a concrete, small
  mechanism).
- **Equivocality is judged by the model.** How does a child *know* a problem is
  equivocal vs uncertain? Needs a stated heuristic ("try the workspace first;
  escalate to a message only after one workspace read failed to disambiguate") —
  otherwise bias workspace-first by default.

The channel question itself is **anchored in practice**: workspace-first +
bounded message-exception is exactly how git-team coordination and blackboard
architectures work, and media richness gives the selection rule.
