# Collaboration Scope Options (A/B/C)

Three candidate scopes for moving from complicated decomposition to complex
coordination. **A is REJECTED**; work continues on **B** and **C**. Either a
parent relays (A), siblings message each other (B), or a bounded shared workspace
with a chair (C). Full decision: [AD-001](../decisions/AD-001.md).

## A. Stay parent-mediated (enhance `stream_children` + `converse`) — REJECTED
All child↔child interaction is relayed through the parent. The parent holds
summaries, decides who needs what, and pushes each child via `converse`;
optionally adds parent-side diagnosis + a mechanical deliverable check (G1/G7).

**Pros:** fits the actor model (no isolation violated, no new contamination
surface); composes with shipped machinery (`stream_children`, `converse`, `kill`,
`status`, `resume`, self-heal); bounded parent context (summaries, not full
contexts); smallest implementation/test surface; partial capability already
shipped (`config.py:265`, `agent.py:1374/1410/1461`).

**Cons:** parent is the bottleneck and single point of failure; every round-trip
burns a parent LLM turn → context rot (needs a max-coordination-turns guardrail
or it becomes monolithic); latency coupling (one child settling wakes the parent
before the next proceeds — inverse of parallelism); "solve together" stays
shallow (intermediate results round-trip through the parent, which sees only
snapshots); steering is prompt-discipline unless G1/G7 become mechanisms.

**Why rejected:** scaling — parent context and turn budget grow linearly with
every round-trip, so the orchestrator degrades into a monolithic agent; and
mixed-context pollution — each settlement summary and converse reply enters the
parent context and cross-contaminates the branches it coordinates.

## B. Sibling mailbox (children message each other)
Direct peer-to-peer: a child sends a message to another child via a runtime
mailbox or shared artifact/commit channels — true information flow where needed,
not through a relay.

**Pros:** genuine collaborative patterns become possible (draft + critique,
handoff, merge-on-shared-state) — the only scope that fully delivers "solve
problems together"; direct flow lowers parent context pressure; scales to many
interacting parts and repeated exchanges (pipelines don't serialize through a
coordinator); enables ensemble patterns (independent reviewers, adversarial
pairs).

**Cons:** violates the core invariant (context encapsulation is a deliberate
quality mechanism; cross-branch contamination becomes possible); needs a
permission model (who may message whom, revocable) → scope creep; new A↔B↔A
churn not caught by the per-agent repeated-call detector → needs cycle detection;
provenance/graph complexity (track inter-agent messages + parent→child edges);
recipient context budget (flooding needs inbox limits, reintroducing a broker);
large test-surface growth, mock determinism harder.

## C. Team/panel (bounded shared workspace + chair)
A fixed, role-scoped group with a designated chair and a shared workspace
(artifact-store directory / branch). Children work in parallel and read each
other's committed artifacts; the chair synthesizes and enforces turn-order.

**Pros:** bounded collaboration (real cross-child flow via shared artifacts,
without unbounded messaging); fits artifact-driven communication (the workspace
is a scoped `ArtifactStore`/commit branch; provenance survives recovery); roles +
chair keep order (no anarchic chat loop; chair arbitrates contention); chair can
be built on `stream_children` + `read_artifact` today.

**Cons:** new abstraction layer (panel lifecycle, membership, chair selection,
termination); shared mutable workspace invites conflicting writes/stale reads —
needs locking/versioning the store doesn't enforce; chair converges toward A if
it relays anything substantive; synchronization semantics undefined (when is a
panel done? quorum, deadline, chair judgment?); group context can blow up unless
truncated each round; heavier than A, riskier than A.

## Scope comparison (quick read)
- Delivers "solve together": A shallow, B fully, C partial.
- Respects context isolation: A yes, B group-scoped (bounded, authorized), C partially.
- Scaling / parent bottleneck: A **fails**, B good, C medium.
- Parent context pressure: A high (pollutes), B low, C medium.
- Implementation size: A — (rejected), B medium–large, C medium.
- Pick if: A —, B collaboration is the product, C shared-state teamwork with guardrails.
