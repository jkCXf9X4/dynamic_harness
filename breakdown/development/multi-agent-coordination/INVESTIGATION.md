---
title: "Investigation — Complicated → Complex: Multi-Agent Coordination"
category: investigation
status: open
summary: >
  Direction work (before implementation) for moving from parallel decomposition
  (problems broken into independent sub-parts) toward multi-agent coordination
  where a parent stands up several children that communicate and solve problems
  together. Parent-mediated relaying (option A) is rejected — see decision log.
---

# Direction: Complicated → Complex Multi-Agent Coordination

## The step being investigated

From **complicated** development — decompose a problem into independent
sub-parts and solve them in isolation — to **complex** development — a parent
stands up multiple children that can *communicate* and *solve together*.

In this codebase that maps to:

| Aspect | Complicated (default today) | Complex (target) |
|--------|------------------------------|------------------|
| Mechanism | `delegate` all-or-nothing batch gather | `agent.stream_children: true` + `converse` + `[child settled]` events |
| Children | Isolated leaves, run to completion | Fire-and-forget, live, steerable mid-flight |
| Parent role | Fan-out → wait → gather → verify → synthesize | Reactive orchestrator: converse, re-delegate, kill stragglers, report early |
| Communication | Child→parent only, via artifacts, at the end | Bidirectional parent↔child, mid-flight |

## What already exists (implemented)

- `agent.stream_children` (config, default false) — `config.py:265`
- Streaming `[child settled]` injection — `core/agent.py:1374`, `:1410`, `:1461`
- `converse` tool (nudge a live child) — `core/tools/agents.py:306`
- `kill` / `status` / `resume` tools for parent-side steering
- Self-heal layers documented — `docs/concepts/self-healing.md`

## Key open questions to resolve before implementation

1. **Scope of "solve together."** True peer/sibling communication does NOT exist.
   The actor model isolates agents (know only parent + children + task). Is the
   target *parent-mediated* coordination (safe within the model) or *peer
   collaboration* (requires relaxing the isolation invariant)?
2. **Cost/context floor.** Streaming burns more parent turns and grows parent
   context as it accumulates settlements + converse exchanges. At what point does
   the orchestrating parent degrade into a monolithic agent (the thing the whole
   architecture avoids)? Need a measurable budget / handoff rule.
3. **Verification is prompt-discipline, not a mechanism.** G1 (acceptance
   criteria never mechanically checked) and G7 (converse-based heal reuses the
   shared `_recover`, not a distinct mechanism) — see `docs/gap-analysis.md`.
   Should "converse → demand better" become a first-class mechanism?
4. **Failure steering.** How does a parent reliably detect a bad child result and
   decide converse vs resume vs kill vs re-delegate — and does the current
   `resume`/self-heal budget cover the multi-round coordination case?
5. **Termination.** When a parent reports/escalates/fails with children still
   running, stragglers are cancelled. Is that the right contract for the complex
   mode, or should settling work be allowed to complete and merge?

## Design space / options to weigh

Three candidate scopes considered. **A is REJECTED** (see decision below). Work
continues on **B** and **C**.

---

### A. Stay parent-mediated (enhance `stream_children` + `converse`) — ❌ REJECTED

All child↔child interaction is relayed through the parent. The parent holds
summaries, decides who needs what, and pushes each child via `converse`. Optionally
adds parent-side diagnosis + a mechanical deliverable/acceptance check (G1/G7).

**Pros**
- Fits the existing actor model — no isolation invariant violated, no new
  cross-branch contamination surface.
- Composes with already-implemented machinery: `stream_children`, `converse`,
  `kill`, `status`, `resume`, self-heal layers.
- Bounded context: the parent carries *summaries*, never full child contexts
  (progressive disclosure holds).
- Smallest implementation + test surface; deterministic tests with mocked LLMs
  stay easy.
- Partial capability already exists and is exercised (streaming mode is shipped,
  `config.py:265`, `agent.py:1374`/`1410`/`1461`).

**Cons**
- Parent is the bottleneck and single point of failure for the whole effort.
- Every coordination round-trip burns a parent LLM turn → parent context rot, the
  exact cost the architecture was built to avoid. Needs a hard guardrail (max
  coordination turns) or it silently becomes a monolithic agent again.
- Latency coupling: one child settling forces the parent to wake up and think
  before the next child can proceed — inverse of parallelism.
- "Solve together" stays shallow: two children that need each other's evolving
  intermediate results must round-trip through the parent, which only sees
  snapshots.
- Steering quality is still prompt-discipline unless G1/G7 become mechanisms.

**Why rejected:** scaling — the parent context and turn budget grow linearly with
every coordination round-trip, so the orchestrator degrades into a monolithic
agent as problems grow; and mixed-context pollution — each child settlement's
summary (and every converse reply) enters the parent context and cross-
contaminates the other branches it is still coordinating. Relaying through a
single parent does not scale and poisons its context. Cut from the design space.

---

### B. Sibling mailbox (children message each other)

Direct peer-to-peer: a child can send a message to another child, either via a
runtime mailbox or via shared artifact/commit channels. True information-flow
where needed, not through a relay.

**Pros**
- Genuine collaborative patterns become possible (draft + critique, handoff,
  merge-on-shared-state) — this is the only scope that fully delivers "solve
  problems *together*".
- Information flows directly → lower parent context pressure (parent no longer
  relays everything).
- Scales to problems with many interacting parts and repeated intermediate
  exchanges; parallel pipelines don't serialize through a coordinator.
- Enables ensemble patterns (independent reviewers, adversarial pairs) that need
  symmetric exchange.

**Cons**
- **Violates the core invariant.** Context encapsulation ("know only parent +
  children + task") is a deliberate quality mechanism — cross-branch
  contamination, the thing isolation prevents, becomes possible.
- Needs a permission model: who may message whom, and can it be revoked? Scope
  creep and branching pollution risk.
- New churn/looping surface: A↔B↔A cascades are not caught by the existing
  repeated-call detector (which is per-agent). Needs its own cycle detection.
- Provenance/graph complexity: runtime must now track inter-agent messages in
  addition to parent→child edges (task graph, telemetry, recovery).
- Context budget for recipients: an agent can be flooded by siblings; needs
  inbox limits / selective delivery, which reintroduces a broker anyway.
- Large test-surface growth; mock-LLM determinism gets much harder.

---

### C. Team/panel (bounded shared workspace + chair)

A fixed, role-scoped group with a designated chair and a shared workspace
(artifact-store directory / branch). Children work in parallel and read each
other's committed artifacts; the chair synthesizes and enforces turn-order.

**Pros**
- Bounded collaboration: real cross-child information flow (shared artifacts)
  without unbounded peer-to-peer messaging.
- Fits artifact-driven communication — the shared workspace is just a scoped
  `ArtifactStore`/commit branch; provenance survives recovery.
- Roles + chair keep order: no anarchic chat loop; each child stays scoped by
  role, chair arbitrates contention.
- Chair can be built on `stream_children` + `read_artifact` today — moderate
  incremental mechanism (a "panel" container + chair policy).

**Cons**
- New abstraction layer on top of runtime: panel lifecycle, membership, chair
  election/selection, termination semantics.
- Shared mutable workspace invites conflicting writes and stale reads; needs
  locking/versioning conventions the artifact store doesn't enforce today.
- Chair converges toward option A in the limit — if the chair relays anything
  substantive, it becomes the relaying parent again.
- Synchronization semantics are undefined: when is a panel "done"? Quorum,
  deadline, chair judgment?
- Group context can blow up: panel deliberation summaries accumulate unless
  explicitly truncated at each round.
- More mechanism + prompt surface to design; heavier than A, riskier than A.

---

## Scope comparison (quick read)

| Criterion | A parent-mediated | B sibling mailbox | C team/panel |
|-----------|-------------------|-------------------|--------------|
| Delivers "solve together" | Shallow | Fully | Partial |
| Respects context isolation | Yes | **No** | Partially |
| Scaling / parent bottleneck | **Fails** | Good | Medium |
| Parent context pressure | High (pollutes) | Low | Medium |
| Implementation size | — (rejected) | Large | Medium |
| Pick if | — | Collaboration is the product | You need shared-state teamwork with guardrails |

## Investigation next steps

- [ ] Read `docs/concepts/delegation-model.md` + `self-healing.md` end-to-end
- [ ] Trace the exact `stream_children` event flow in `core/agent.py`
- [ ] Enumerate failure/steering cases (empty artifact, failed child, looping
      child, straggler) and map each to converse/resume/kill/re-delegate
- [ ] Decide B vs C scope; write a concrete target behavior spec
- [ ] Define the cost guardrail (max turns / shared-workspace budget)
- [ ] Flag the G1/G7 mechanism gap as a prerequisite or explicit non-goal
