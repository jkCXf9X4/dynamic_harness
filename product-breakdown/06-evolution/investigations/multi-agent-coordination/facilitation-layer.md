# Facilitation Layer: Facilitation Yes, Facilitator Agent No

Should the collaboration channel have a **facilitator** to mitigate negative
effects, or stay **pure child-to-child**? Theory resolves this as a three-layer
stack in which the "facilitator" is almost entirely *mechanical structure*, with
a *sparse* arbitration role only at conflict. Decisions:
[AD-004](../decisions/AD-004.md). Ostrom evidence:
[ostrom-principles.md](ostrom-principles.md).

## The three layers (recommended)
- **L0 — Pure peer-to-peer (steady state).** Workspace reads/writes + bounded
  message channel, direct child↔child, parent absent. Covers ~all routine
  coordination. The "context over control" default.
- **L1 — Mechanical facilitation (the invisible facilitator).** All policy/code,
  zero LLM tokens, no bottleneck: boundaries/membership (REQ-1/2) — Ostrom #1;
  monitoring via append-only writes + provenance (Repository commits) every child
  can see — Ostrom #4 ("monitors are the users"); graduated sanctions (REQ-6
  caps, REQ-9 loop detection) — Ostrom #5: warn → tighten → hard stop → notify,
  not instant failure; round/cadence (settle-then-yield as "fetch new writes once
  per turn"); write-conflict conventions (append/review over overwrite).
- **L2 — Sparse arbitration (the low-cost local arena).** The only *agent*
  facilitation, existing solely for conflicts L0/L1 cannot resolve:
  child↔child negotiate over the **rich** channel first (media richness:
  equivocality is what messages are for); an *unresolved* dispute → single
  escalate to the **parent**, who arbitrates once and is done (arbitrate,
  converse, disconnect, or dissolve the group). This is Ostrom #6 (rapid,
  low-cost local arena) + Netflix's "step in at risk points" + Hackman's
  coaching-at-transitions, and is already REQ-8. The parent is the arena
  **because it already holds authority** — a peer-chair agent would defer to it
  anyway.

## When a dedicated facilitator agent is actually worth it (edge case only)
Very large groups (many children) or a parent saturated with other work, where
sparse parent arbitration would serialize. Then a **content-neutral sibling
"chair"** is a defensible *optional* enhancement — scoped to L2-style arbitration
(structure/process, no content relay), its decisions parent-overridable.
Default: don't build it.

## Answer to the question
- **Pure child-to-child with zero facilitation: no.** The commons-tragedy trap —
  no monitoring, no graduated sanctions, no conflict resolution; exactly the
  churn/contention risks that motivated the guardrails.
- **An always-on facilitator (agent): no.** It repeats option A's cost model,
  duplicates what policy already does better, and violates content-neutrality.
- **A hybrid: yes.** Pure peering for the steady state + a mechanical "invisible
  facilitator" layer (policy: monitoring, caps, sanctions, provenance) + sparse
  parent arbitration as the low-cost conflict arena. Ostrom's design principles,
  the facilitator ideal of "structure/process without content authority," and
  Hackman's minimal coaching — all three in agreement.
