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

## Deep dive: B — sibling collaboration under a common parent

Investigating how to enable real collaboration (B) while containing its cons, by
**constraining peer-to-peer communication to siblings that share a common
parent** ("children of one parent form a team").

### The key idea

"Team membership" is defined by **shared parentage** — a concept the runtime
already tracks (`task.parent_id`, the task graph). No new structural entity is
needed: a collaboration group *is* the parent-owned subtree. Communication is
only allowed between agents that share a parent, and the parent is that group's
natural authority (can authorize, observe, and revoke channels).

### Enabling mechanism — mostly plumbing that already exists

The delivery machinery is already present and used by `converse`:

| Piece | Where it exists | Role in B |
|-------|-----------------|-----------|
| `converse` tool → `continue_with_input(agent_id, message)` | `tools/agents.py:306`, `agent.py:683` | A child pushes a message to a live sibling; wakes it |
| `submit_input` / `_inject_queue` / `_inject_event` | `agent.py:1246-1267` | Message queued while busy; interrupts a child waiting on its own children |
| `get_other_agent` | `agent.py:1500` | Address resolution — today ANY agent, needs scoping |
| Status gates (conversable = completed/running) | `policies/permissions.py:51` | Eligibility for receiving messages |
| Streaming `[child settled]` events | `agent.py:1374/1410/1461` | Parent-aware event hook where sibling channels attach |

So **B is not a from-scratch build** — it is (1) a new *scope rule* on who may
message whom, (2) a *delivery/budget policy*, and (3) *loop detection + parent
visibility* around exchanges. `converse` already proves a live child can be
pushed mid-run.

### How common-parent scoping mitigates each of B's cons

| B con | Mitigation via "siblings of a common parent" | Mitigated? |
|-------|---------------------------------------------|-----------|
| **Violates context encapsulation (cross-branch contamination)** | Contamination is confined to a trusted sibling set that shares a coordinator; no global graph addressing, so other subtrees are never touched. Keep progressive disclosure: the recipient sees a *summary* of the message (like a settlement), not the sender's context. | **Mostly** — bounded + authorized, but the invariant is still softened for the group |
| **Needs a permission model (who may message whom)** | Scope collapses to "same parent." Default **denied**; enabled per-delegation (opt-in `collaborate=True` on `delegate`, or a parent-declared group). The parent is the existing authority — no new global permission system. | **Strongly** — no new permission subsystem |
| **Churn / looping (A↔B↔A not caught)** | Cycles are bounded to a small, known edge set (the subtree). Runtime can track exchanges per sibling-pair and enforce a per-pair / per-round cap with a "must settle and yield" rule. Still new detection, but the search space is tiny and known to the runtime. | **Partially** — needs per-pair cycle detection, but tractable |
| **Provenance / graph complexity** | Sibling edges are internal to the parent's subtree; the parent remains the provenance anchor. Log exchanges as telemetry events tagged with the common parent task_id; artifact/commit provenance is unaffected (children still own their artifacts). | **Largely** |
| **Recipient inbox flood** | Bounded mailbox per agent + per-sibling budget cap; the parent can revoke/close a channel. | **Mostly** |
| **Large test surface** | Restricted to parent + 2–3 children groups → tractable mock-LLM scenarios. | **Partially** |

### Collaboration patterns this unlocks

- **Handoff** — A produces an intermediate artifact, sends `artifact_id` to B.
- **Critique / peer review** — B reviews A's artifact and returns feedback; A
  revises. Internal QA *without* polling the parent's context.
- **Combine / merge** — children merge partial results before reporting to the
  parent (reduces parent synthesis load).
- **Ask a sibling for help** — A blocked on missing knowledge that a peer has
  (the documented `ask` pattern, but peer-to-peer instead of human/parent).
- **Coordination on a shared target** — children working on parts of one
  subsystem exchange updates to avoid conflicting writes.

### Residual cons and new concerns (what scoping does NOT fix)

- **Group-internal contamination remains.** Siblings' contexts absorb each
  other's material. Mitigations: summary-only delivery, per-recipient message
  caps, and the fact that the parent still verifies final results (VERIFY).
- **Adverse sibling data.** One child can mislead another. Each child must retain
  autonomy — a sibling message is *input*, not authority; a child can ignore or
  escalate a suspicious peer to the parent.
- **When is messaging legal?** Only while the parent is active/streaming?
  Channels to a *settled* sibling should be closed (read its artifact instead —
  existing behavior). Define delivery vs lifecycle rules.
- **Parent visibility / load.** If the parent must read every exchange, that's
  option-A pollution again. Design: parent is notified of *events* (channel
  opened/closed, escalation, over-budget) but not content by default; content
  summaries are pull-only via `read_artifact`/`status`.
- **Is B still distinguishable from C?** With a common parent, B begins to look
  like a lightweight C without a mandatory chair relay. Decision point: does the
  parent *relay* (A, rejected) or *oversee* (B/C)? Oversight-only keeps B's
  scaling and isolation-vs-parent properties while enabling collaboration.

### Requirements for B-curated (consolidated)

Guardrails from the earlier deep-dive, strengthened into concrete requirements by
folding in the 8 design implications from the management-theory report
(`management-theory-communication-facilitation.md` §7). The theory behind each
requirement is in brackets.

**Group / who may collaborate**
- REQ-1 **Explicit membership.** The collaboration group is a first-class scoped
  concept: "children of a common parent, plus explicit membership". Nobody is
  ambiguously on the team — a parent eithe introduces you or it doesn't.
  [Hackman: real team; Project Aristotle: structure & clarity]
- REQ-2 **Scope rule (default deny).** Peer messaging is denied unless the parent
  introduced the pair (delegation-time `collaborate_with=[...]` or mid-run
  `introduce(agent_a, agent_b, note)`). Enforce in `get_other_agent`/a new policy
  object — the permission is an *edge*, not a global right.
  [TMS directory; bounded rationality]
- REQ-3 **Introductions are requestable and declinable.** A blocked child may
  `ask` for a pointer; the parent routes (knowledge broker). A child may decline
  an introduction with no penalty.
  [Edmondson: psychological safety; Wegner: directory lookup + route]

**Context, not content**
- REQ-4 **`introduce` ships metadata + why only.** The injection carries sibling
  ID, a one-line rationale, and a scope-norm reminder. It never carries a
  payload. Content stays in artifacts.
  [Netflix: context over control; Conway's inverse]
- REQ-5 **Parent context is protected by construction.** The parent's per-child
  visibility is summarize-only (settlements, statuses, artifact summaries); any
  content curiosity is pull-only via `read_artifact`. The parent is never
  awakened for routine peer traffic.
  [transaction costs; bounded rationality; boundary-spanning]

**Norms as policy, not prose**
- REQ-6 **Norms are policy objects, not prompt text** (mirroring
  `ToolPermissionPolicy`): per-sibling-pair message cap + per-round cap + hard
  stop, advisory-only delivery semantics, settle-then-yield, escalation-on-
  conflict, delivery only summary-only.
  [Hackman: enabling structure — norms; Thompson: least-cost coordination]
- REQ-7 **Cadence substitutes for control.** Settlement events are the
  "standup"; a "persist a checkpoint/artifact before you speak again" rule gives
  rhythm without permission.
  [rituals over control — agile]

**Steering and safety (parent = broker, not content reader)**
- REQ-8 **Risk-point coaching only.** The parent is awakened only for: new
  connection, over-budget exchange, escalation, or a child lacking context (the
  Netflix "step in" list). It does not check in between.
  [Hackman: periodic coaching; Netflix: step in at risk points]
- REQ-9 **Loop detection.** Per-pair exchange counter + settle-then-yield;
  breach → close channel + notify parent. Scoped to the group edge set (small,
  known to the runtime).
  [repeated-call detection generalization]
- REQ-10 **Lifecycle.** Channels close when the parent settles or is killed;
  settled siblings are read-only targets (no messaging). Cost of a bad hookup
  (mis-connection, ghosting) is one wasted message.
  [transaction costs — cheap failures]
- REQ-11 **Dissent is engineered.** Seed at least one independent or contrarian
  link per material group (a verifier, or a cross-scope child), and periodically
  connect *non-overlapping* siblings to bring novel input — the systemic
  antidote to group-think.
  [cognitive diversity; Granovetter weak ties; Netflix: farming for dissent]
- REQ-12 **Child autonomy is protected.** An incoming sibling message is
  advisory, not authoritative; a child may ignore it, challenge it, or escalate
  to the parent. Failure to speak up (hiding bad news) must never be cheaper
  than surfacing it.
  [psychological safety; Edmondson: failure framing is informational]

**Commons governance (from the facilitation-layer analysis, Ostrom)**
- REQ-13 **Graduated sanctions, not instant failure.** Violations of channel/
  workspace rules follow a ladder: warn → tighten (reduce cap) → hard stop →
  notify parent. Proportional, observable, reversible.
  [Ostrom design principle 5]
- REQ-14 **Conflict-resolution arena.** Disputes resolve at the lowest cost:
  child↔child negotiation on the rich channel first; if unresolved, a single
  escalation to the parent arbitrates once (arbitrate / converse / disconnect /
  dissolve group). Resolution is recorded to provenance.
  [Ostrom principle 6 — "rapid access to low-cost local arenas"]
- REQ-15 **Monitoring is distributed, not appointed.** Workspace writes are
  append-only and committed (provenance), so any group member can audit any
  other's contributions at near-zero cost. No dedicated monitor agent.
  [Ostrom principle 4 — "monitors are the users"]

---

## Refining B: "context over control" — the parent introduces, not mediates

Evaluating whether the parent should **inject the child IDs** (introduce siblings
to each other) when it deems it beneficial — while *not* overseeing the exchanges
that follow. Verdict: **yes, this is the right shape of B**, and close to fully
supported by existing plumbing.

### The mechanism: `introduce`, a one-time context injection

The parent does not relay content. It performs a single cheap act — giving each
child the *other's ID plus one line of "why you might benefit"* — and steps back.

- **Static / delegation-time:** `delegate(description, collaborate_with=[...],
  intro_note=...)` sets up a team with known dependencies up front ("set up the
  team").
- **Dynamic / mid-run:** a parent tool `introduce(agent_a, agent_b, note)` when
  it spots an intersection or a blocked child asks for help ("if it deems it
  beneficial"). Streaming mode (`[child settled]`) is what makes this adaptive.
- After the injection, siblings use the existing `converse`/`continue_with_input`
  plumbing directly — no parent round-trip per message.
- Parent *can* revoke a connection (one call) — team composition is mutable.

### Can the parent decide *without overseeing*? Yes — signals, not content

The parent needs no access to sibling conversations. The observable signals are
already streaming to it by design:

| Signal | Already visible to parent? |
|--------|---------------------------|
| Child status (running / completed / failed) | `status` tool, `[child settled]` events |
| Child artifact *summaries* (headline / summary_200) | VERIFY step reads these by design |
| Blocked child (`ask` for help / pointer) | `ask` / escalation events |
| Scope overlap (same files, same target) | deducible from delegation descriptions + paths |

Reading **summaries, not content**, is exactly the boundary-spanning visibility a
manager has (weekly report, not inbox access). Hackman's framework calls this a
*real team boundary*: the parent sees what crosses the boundary, not what happens
inside it.

### Why the injection is not micromanagement (and relaying was)

**Context over control (Netflix Culture Memo).** "We expect managers to practice
*context not control* — giving their teams the context and clarity needed to make
good decisions instead of trying to control everything themselves." The injected
ID + why-it-matters is pure context; the parent supplies *alignment* (directions,
roles, connections) and then expects **highly aligned, loosely coupled** execution
— peers coordinate directly because they share enough context to do so. Option A
(rejected) *was* control: the parent approved every exchange, creating exactly the
kind of manager-caused latency and context pollution that Gary Hamel describes as
management's "hefty tax" (HBR, "First, Let's Fire All the Managers").

### Management-theory echoes (how the parent role maps)

| Frame | Source | What it says | Parent in B-curated |
|-------|--------|--------------|---------------------|
| Context not control / people over process | [Netflix Culture Memo](https://jobs.netflix.com/culture) | Give the *why*, not the approval; few, not many, senior decisions | Introduces, never relays |
| Highly aligned, loosely coupled | Netflix | Alignment from leadership, freedom to act directly | Aligns via intro; children self-coordinate |
| Management = "hefty tax" | [Hamel, HBR 2011](https://hbr.org/2011/12/first-lets-fire-all-the-managers) | Every relay/approval adds latency + loss | Rejected option A — relay gone |
| Real team + enabling structure | [Hackman via HBR 2009](https://hbr.org/2009/05/why-teams-dont-work) | Effective teams need membership, direction, and structure/norms — not hovering | Sets membership (intro) + norms (budgets), then steps back |
| Expert coaching is periodic | Hackman | Coaching at starts/transitions, not continuous | Parent coaches at connect/disconnect/escalate points only |
| Shared consciousness → empowered execution | McChrystal, *Team of Teams* | Decentralized action needs shared context links | Injection = shared consciousness; direct peer comm = empowered execution |
| Autonomy fuels motivated, better work | Amabile & Kramer, "The Power of Small Wins" (HBR 2011) | Progress + autonomy → higher-quality output | Children don't stall behind a gatekeeper |
| Minimize transaction costs | Coase / Williamson | Route around the central bottleneck when cheap direct links exist | One-time intro cost amortizes vs per-message relays |

### Risks and the honest cons

- **Mis-connection.** The parent's judgment runs on summaries; it can introduce
  children whose overlap is actually a conflict. Guardrail: an introduction is an
  *invitation, not a mandate* — a child may decline, and the parent can
  disconnect. Cost of a bad hookup is tiny.
- **Group-think / echo chamber.** Siblings may reinforce a shared wrong
  direction, silently. Guardrails: keep at least one child independent of the
  group (a verifier), and the parent deliberately "farms for dissent" (Netflix) —
  connect *unrelated* children occasionally, sample counterevidence.
- **Ghosting.** A child ignores an introduction. Cheap — one wasted message.
- **Scope-softening, but now curated.** Isolation is still softened for the
  group, but edges are **parent-chosen**, one at a time, and revocable — not an
  open bus. Accidental cross-branch contamination drops to near zero compared
  with unconstrained B.
- **Parent-load stays event-only.** If the parent later starts reading exchange
  *content* to "help", it decays back into the rejected option A. Enforced by
  design: content is pull-only, and default oversight is one event line.

### What this changes in the B-vs-C picture

With introductions, B and C nearly converge: a parent-declared group with
introduced siblings *is* a lightweight panel, differing only in the exchange
model (direct peer messages vs shared mutable workspace). The decision becomes:
- **B-curated** — peer *messages* are the collaboration channel (summary-only,
  advisory). Simpler, preserves per-child lifecycle/tooling.
- **C/panel** — a shared *workspace* is the channel (artifact-store dir).
  Stronger for persistent shared state, but needs write-conflict conventions the
  store doesn't enforce today.

Both keep the parent in the **enabler** seat ("context over control"), neither
requires the parent to oversee content.

---

## Channel decision: shared workspace vs sibling messages

After REQ-1–12, the remaining open design choice is the **collaboration
channel**: do introduced siblings exchange via peer *messages* (B-curated) or
via a shared *workspace* (C)? The management material from the report + the two
additional theories researched for this decision provide a strong anchor.

### Correlations from the material and from organizational practice

**1. Media Richness Theory (Daft & Lengel, 1986)** — the sharpest fit. Richness
is the medium's ability to "change understanding within a time interval."
Managers should match **medium richness to message equivocality**:
- *Equivocal* coordination (ambiguity, conflicting interpretations, negotiation,
  "why is this wrong?") needs **rich** media — fast feedback, personal focus
  (≈ direct messages/back-and-forth).
- *Uncertain* coordination (a value, a finding, a file that already exists
  somewhere) needs only **lean** media — written, asynchronous, reusable
  (≈ shared workspace / artifacts).

Big-cheat version: **pass information through the workspace; negotiate meaning
through messages.** Using too-lean media for equivocal tasks causes more
difficulties than using too-rich media for lean tasks — so when in doubt, the
workspace (lean) is safe **only for non-equivocal** exchange.

**2. Boundary objects (Star & Griesemer, 1989)** — the workspace artifact *is*
the classic collaboration medium. Boundary objects "allow coordination without
consensus": plastic enough for each party's local needs, robust enough to keep a
common identity. The same shared artifact coordinates specialists who never need
to agree on interpretation — precisely the cross-role child case. Direct
negotiation between specialists is a *worse* path: the boundary-objects
literature (Kertcher & Coslor) found pre-stabilization periods *forcing* direct
cross-boundary negotiation are "frustrating" and escalate friction.

**3. Blackboard / distributed AI (Hearsay-II lineage)** — the canonical
multi-agent pattern is specialist modules coordinating *through a shared
blackboard* and never messaging each other directly. Where the "team" is
independent specialists contributing to a joint result, the proven substrate is
a shared store, not a chat network.

**4. Modern collaborative engineering (git / PR / code review)** — practice has
settled the question empirically: teams coordinate **on the artifact** (repo,
diff, PR), and messages ride *on top of* artifacts (review comments anchored to
lines) rather than replacing them. The artifact is the hub; chat is the overlay.

**5. Thompson's coordination mechanisms (1967)** — least-cost rule: prefer the
cheapest mechanism that works (shared artifacts / plans) and escalate to mutual
adjustment (direct messages) only when the cheaper one fails. Complementary to
media richness: cost-ordered, workspace first.

**6. Reconciling with the earlier management survey:**
- **TMS (Wegner)** resolves the apparent tension: the *store* is the artifact;
  the *directory* ("who knows what") and *retrieval* ("ask the right person") are
  messages. They are two layers, not rivals — messages **route to** artifacts.
- **Hackman's norms** and **transaction costs** both prefer artifacts: an opaque,
  versioned, reusable artifact is cheaper per use than an interrupted recipient's
  context consumption.
- **McChrystal's empowerment** is served by workspace transparency (shared
  dashboard), with messages as the exceptional live call.
- **Amabile/autonomy & psychological safety** are *supported*, not threatened, by
  a workspace: children act on their own against a shared surface of truth, and
  can surface disagreement by writing, not just by pinging.

### The decision: workspace-primary, messages-as-exception

**The collaboration channel is a shared, scoped workspace (a sibling-visible
artifact area) as the primary substrate; peer messages are the scarce, bounded
exception used only for *equivocal* coordination** (clarify intent, negotiate an
answer, ask where knowledge lives — then go read the artifact).

Decision rules (state these in the spec):
1. **To share a result, a finding, or a constraint → write/read the workspace.**
   No message needed. The artifact is the boundary object; "coordination without
   consensus" applies.
2. **To route or ask "who knows this?" → a message that points to the workspace**
   (ID + why), not a payload (mirrors REQ-4). TMS retrieval.
3. **To reconcile conflicting interpretations / demand a revision → messages**,
   the rich channel, but bounded per-pair and hard-stopped on over-budget
   (REQ-6, REQ-9) when the exchange should escalate to the parent or a fresh
   worker.
4. **Default source of truth is the workspace.** A child that read the artifact
   disagrees with a sibling's message — the artifact wins; escalate if it
   matters (REQ-12, existing VERIFY).

Rationalisation against the criteria that rejected A:
- The parent relays nothing (still true — messages and artifacts both bypass it).
- Recipient context is protected: most coordination is *pull* (read what you
  need) rather than *push* (interruptive message). This attacks the exact
  "mixed-context pollution" that killed option A, one level deeper.
- Churn/loop risk shrinks: the bounded message channel sees only equivocal
  exchanges; the workspace is naturally asynchronous and non-interruptive.

### What this does to B vs C, and what still needs investigation

This is a **hybrid** that adopts C's substrate for information exchange and B's
messages for equivocal negotiation — effectively choosing both, with a selection
rule. Residual investigation items the theory does **not** fully decide:
- **Workspace mechanics.** A scoped directory in `ArtifactStore` needs
  write-conflict conventions and visibility rules (who may read/write what, when)
  that the store does not enforce today (C's known gap). Blackboard/git practice
  (append-only + review) suggests the form; the runtime policy needs defining.
- **Cadence/round semantics.** A workspace is asynchronous; "which children are
  waiting on a sibling's write" is a new lifecycle question (settle-then-yield
  becomes "fetch newly-settled siblings once per turn" — a concrete, small
  mechanism).
- **Equivocality is judged by the model.** REQ odd: how does a child *know* a
  problem is equivocal vs uncertain? Needs a stated heuristic (e.g., "try the
  workspace first; escalate to a message only after one workspace read failed to
  disambiguate") — otherwise the bias should be workspace-first by default.

These are flagged as open below. The channel question itself is **anchored in
practice**: workspace-first + bounded message-exception is exactly how git-team
coordination and blackboard architectures work, and media richness gives the
selection rule.

---

## Facilitation layer: facilitation yes, facilitator agent no

Question: should the collaboration channel have a **facilitator** to mitigate
negative effects, or stay **pure child-to-child**? The theory resolves this as a
three-layer stack in which the "facilitator" is almost entirely *mechanical
structure*, with a *sparse* arbitration role only at conflict.

### The sharpest anchor: Ostrom's commons governance

Elinor Ostrom's Nobel-winning analysis of long-lived shared-resource groups
("common-pool resources") is the direct analogue of a shared artifact workspace,
and it is emphatic that sustainable self-governance is **neither anarchy nor a
boss**. Communities that *thrive* do so through explicit institutional design
(design principles, *Governing the Commons*, 1990; @Ostrom 2009 Nobel):

1. **Clearly defined boundaries** — who may use the resource (≈ REQ-1 membership).
2. **Congruence with local conditions** — rules fit the work.
3. **Collective-choice arrangements** — those affected may modify the rules.
4. **Monitoring** — monitors who are *accountable to the users*, "or are the
   users" (≈ distributed self-monitoring, not a dedicated overseer).
5. **Graduated sanctions** — proportional penalties (a ladder, not instant death).
6. **Conflict-resolution mechanisms** — "rapid access to low-cost local arenas."
7. **Recognition of rights to organize** — the group may govern itself.
8. **Nested enterprises** — layered governance.

The vital distinction: these are **mechanisms, not a person**. The runtime's
rules/caps/provenance *are* the institution; no facilitator agent is required to
enact them. Pure child-to-child with no structure is the "tragedy of the
commons" trap — in workspace terms: unmonitored overwrites, escalating message
loops, and one hallucinating child corrupting shared artifacts.

### The facilitator literature confirms: it's structure and process, not a relay

A facilitator by definition (Doyle, Bens, Kaner) is **content-neutral** and
"contributes structure and process" — it does **not** take positions on content
and does **not** carry the message. In a runtime, "structure and process" are
**code (policy objects)** — REQ-6 already gives us the norms-as-policy principle,
and the cost-free, bottleneck-free realization is an *invisible facilitator*.
A facilitator **agent** would, by contrast, (a) burn tokens on every interaction —
the option-A cost model again, (b) lack authority over siblings and therefore
escalate anyway — a double hop, and (c) become a single point of failure and
lifecycle burden. The theory says the job it would do is already done cheaper by
policy.

### The three layers (recommended)

**L0 — Pure peer-to-peer (steady state).** Workspace reads/writes + bounded
message channel, direct child↔child, parent absent. Covers ~all routine
coordination. The "context over control" default.

**L1 — Mechanical facilitation (the invisible facilitator).** All of it is
policy/code, zero LLM tokens, no bottleneck:
- Boundaries/membership (REQ-1/2) — Ostrom #1.
- Monitoring via append-only writes + provenance (Repository commits) that every
  child can see — Ostrom #4 ("monitors are the users").
- Graduated sanctions (REQ-6 caps, REQ-9 loop detection) — Ostrom #5: warn →
  tighten → hard stop → notify, not instant failure.
- Round/cadence (settle-then-yield as "fetch new writes once per turn").
- Write-conflict conventions (append/review over overwrite).

**L2 — Sparse arbitration (the low-cost local arena).** The only *agent*
facilitation, and it exists solely for conflicts L0/L1 cannot resolve:
- Rule: child↔child negotiate over the **rich** channel first (media richness:
  equivocality is what messages are for); *unresolved* dispute → single escalate
  to the **parent**, who arbitrates once and is done (arbitrate, converse,
  disconnect, or dissolve the group).
- This is Ostrom #6 (rapid, low-cost local arena) + Netflix's "step in at risk
  points" + Hackman's coaching-at-transitions, and it is already REQ-8. The
  parent is the arena **because it already holds authority** — a peer-chair agent
  would need to defer to it anyway.

### When a dedicated facilitator agent is *actually* worth it (edge case only)

Very large groups (many children) or a parent saturated with other work, where
sparse parent arbitration would serialize. Then a **content-neutral sibling
"chair"** is a defensible *optional* enhancement — but it must be scoped to
L2-style arbitration (structure/process, no content relay), and its own decisions
must remain parent-overridable. Default: don't build it.

### Answer to the question

- **Pure child-to-child with zero facilitation: no.** It's the commons-tragedy
  trap — no monitoring, no graduated sanctions, no conflict resolution; exactly
  the churn/contention risks that motivated the guardrails.
- **An always-on facilitator (agent): no.** It repeats option A's cost model,
  duplicates what policy already does better, and violates content-neutrality.
- **A hybrid: yes.** Pure peering for the steady state + a mechanical
  "invisible facilitator" layer (policy: monitoring, caps, sanctions,
  provenance) + sparse parent arbitration as the low-cost conflict arena. This
  is Ostrom's design principles, the facilitator ideal of "structure/process
  without content authority," and Hackman's minimal coaching — all three in
  agreement.

---

## Scope: orchestration feature or general capability?

Question: is child layer-by-layer collaboration an *orchestration* feature,
or a *general capability every agent possesses*? Hackman's five conditions — and
especially #1 (real team) and #2 (compelling direction) — are the ground the
answer sits on.

### The answer: founding is boundary-scoped, participation is universal

Split the capability along the two halves the theory already separates —
**leader sets conditions, members execute** (Hackman) and **mechanisms are
institutions, not persons** (Ostrom):

| | Founder (set up the team) | Member (work in the team) |
|---|---|---|
| Who | Any **node with children** — at that layer | **Every agent, at any depth**, leaves included |
| Acts | `collaborate_with` / `introduce`, write the charter, open the workspace, arbitrate | read/write the team workspace, bounded messages, negotiate, escalate |
| Grounding | Hackman #1/#2 are *leader-provided*; only the parent has the decomposition view | Hackman #1 is about the *team*, not the level; leaves are frequently the interdependent parties |

**Why founding is parent-scoped, not general:**

- **Hackman's conditions are setup acts.** Membership (#1) and direction (#2)
  can only be declared by someone who (a) sees the whole sibling set and its
  interdependence, and (b) has authority to bound it. In the actor model only
  the parent meets both — siblings never see each other until introduced
  (`agent.py:1500 get_other_agent` is the only lookup, and it is unscoped
  today). A leaf literally cannot found a team it cannot see.
- **The TMS directory lives at the parent.** Only the parent knows "who knows
  what" across its children (Wegner); introduction is a directory-routing act.
- **Naturally layer-scoped, no role string needed.** Founding self-restricts to
  nodes that *have* children (`self.children`). This is cleaner than the role
  tag: collaboration scales with delegation by construction — every subtree that
  spawns interdependent children gets a team; independent fan-out needs none.
- **General founding would re-open option A/unbounded B.** For an arbitrary
  agent to introduce arbitrary others it would need global addressing and global
  authority — the exact unconstrained-B shape we rejected.

**Why participation is universal (leaves included):**

- **Interdependence is not depth-dependent.** Two leaf siblings each holding
  half of a result are exactly the Hackman "real team": bounded membership,
  interdependent task, shared responsibility. They must collaborate *without*
  either becoming an orchestrator.
- **It keeps trees shallow.** Leaves that can hand off via the team workspace
  stay leaves. Forcing every collaborating leaf to delegate would grow the tree
  (each handoff becomes a delegation) — against the stated "prefer broad,
  flat, shallow trees" discipline.
- **Nested enterprises (Ostrom #8).** A node is simultaneously a *member* of
  its parent's team and, if it has children, the *founder* of its own nested
  team. Participation must therefore be universal for the nesting to compose
  "layer by layer."
- **It is safe because tool-safety is scoped.** Team workspace read/write is
  scoped to the team's workspace directory; messages are bounded and
  parent-authorized. A leaf gains capability, not privilege.

### The collaboration setting = Hackman's conditions, instantiated per layer

A concrete "collaboration setting" object (a team workspace opened by the
founding parent) should map 1:1 onto Hackman's five — the first two being the
*non-negotiable* core the user identifies:

| Hackman condition | The collaboration-setting realization |
|---|---|
| **1. A real team** | Membership is bounded and explicit: `collaborate_with=[...]` is the boundary. Nobody is unclear about who is on the team. (REQ-1) |
| **2. A compelling direction** | A **team charter** posted as the workspace's first artifact: the collective objective, why it matters, acceptance criteria. Challenging, clear, consequential. Doubles as the mechanical G1 acceptance target to verify team output against. |
| 3. Enabling structure | Team norms as the policy object (REQ-6) + per-member roles already set by delegation. |
| 4. Supportive context | The scoped workspace + provenance + budgets the runtime provides (REQ-15). |
| 5. Expert coaching | The parent's L2 arbitration — sparse, at transitions/conflicts (REQ-8, REQ-14). |

Because founding is boundary-scoped, this object is **the same class at every
layer**: each parent instantiates one for its interdependent children, and a
child that is itself a parent instantiates a nested one for its own children —
"facilitate child layer-by-layer collaboration" *is* the recurrence of this
object down the tree. Directives to children and charters alone do not make a
team; the *bounded, scaffolded setting* is what Hackman #1/#2 formalize.

### Relationship to the orchestrator's existing workflow

Collaboration is an **orchestration modality at decomposition time**, not a
separate system. The orchestrator's loop gains a team-forming variant:

```
ANALYZE → DECOMPOSE → [form team IF interdependent] → DELEGATE
        → VERIFY (on the workspace) → SYNTHESIZE → TERMINATE
```

- **Independent units** → plain parallel delegation, unchanged.
- **Interdependent units** → the parent *founds a team* among them (context,
  not control): declare membership, post the charter (direction), open the
  workspace, introduce. Then it *stays out* of the steady state — the children
  coordinate in the workspace themselves; the parent's VERIFY checks the
  workspace output against the charter's acceptance criteria (which closes G1's
  "verify is only prompt-discipline" gap), and its SYNTHESIZE consumes settled
  team artifacts.
- The parent's role in the team is the **coach-transitions-only** role
  (Hackman #5), never a relay.

So: the *setting* is an orchestration output at each boundary; the *work done
inside it* is general. That division is exactly Hackman's — the leader sets the
conditions, the team performs — and it is what makes "child layer-by-layer
collaboration" possible without reintroducing a relaying bottleneck at any
level.

### Codified: one distributed capability, two facets, structure-driven activation

Concluding statement — the capability is **one object distributed to every
node**, carrying **two facets**, where **activation is structural, not
role-based**:

```
CollaborationCapability (on every Agent node)
 ├── MEMBER facet   — always available; active iff a parent introduced you
 │     · receive introduction / decline
 │     · read/write the team workspace (scoped)
 │     · bounded messages to introduced siblings
 │     · negotiate / escalate
 └── FOUNDER facet  — always available; active iff you have children
       · declare membership (collaborate_with / introduce)
       · post the team charter (direction + acceptance)
       · open the nested team workspace
       · arbitrate conflicts (L2 arena)
```

The design consequences:

1. **No class split, no role string, nothing to promote.** A node is a *member*
   of its parent's team and, once it delegates, automatically a *founder* of its
   own nested team — the same capability object, both sides idle until structure
   activates them. Layer-by-layer collaboration is *compositional by
   construction*: deeper subtrees inherit the tooling with zero reconfiguration.
   Mirrors how the runtime already treats leaf vs orchestrator as a per-task
   property of the same `Agent` class.
2. **Distribution ≠ privilege.** The capability is uniform; the *enforcement*
   stays at the boundaries: member writes are scoped to the team workspace they
   were introduced to; founder actions require `self.children` non-empty. A node
   with no team and no children holds the object but no active workspace — it is
   inert, not powerful.
3. **The founding decision still lives at each boundary.** Uniform machinery
   changes *where the code lives*, not *who decides membership*. Membership and
   charter are still declared by the parent of that layer (authority +
   decomposition view); the capability object is just how that authority is
   *executed* with the same tooling everywhere.
4. **Implementation shape.** One mixin/interface `CollaborationCapability`
   bundled into `Agent` (like the tool set), backed by runtime-registered team
   workspaces; the member/founder split is enforced by the scoping policy
   (REQ-1/2), not by separate agent classes.

---

## Simplicity review: the spine — links + delivery + pointers

The spec over-modeled. The advanced features (team object, charter, norms,
sanctions, workspace, arbitration ladder) are **policy layers that can sit on a
much smaller spine** — and the spine is mostly *existing machinery*.

### The spine (three primitives, all present in the codebase today)

1. **Links** — ONE new structure: a runtime registry of authorized peer pairs.
   ```python
   self._links: set[tuple[str, str]] = set()   # unordered, normalized (min,max)
   ```
   Plus the *only* authorization rule: **a `link(a, b)` call is accepted iff the
   caller is the common parent of both** — `a.parent is caller and b.parent is
   caller`. That's it. No team object, no membership dict to maintain, no
   lifecycle FSM: membership *is* the link set, authorization *is* the
   parent-of-both check (O(1) via `target.parent`).
2. **Delivery** — reuse the existing message path: `converse` →
   `continue_with_input` → `_inject_queue`/`_inject_event` (`agent.py:327/683/
   1246`). A sibling message is just a `converse` whose eligibility gate becomes
   `(agent_a, agent_b) in self._links` (in addition to today's parent↔child).
   `[sibling {id}] {summary}\nPointer: {artifact_id|result_id}` — summary-only,
   pointer-carrying, exactly like initiatives already write.
3. **Content** — reuse existing pointer machinery: the recipient pulls the full
   body via `read_artifact` / `result_read`. **No workspace needed for MVP**:
   artifacts/result snapshots are already shared, immutable, display-scoped
   state; the missing piece was only *discovery* ("who produced what"), which
   the pointer in the message provides.

Lifecycle is then free: `link` edges die implicitly when the parent settles
(deleting the subtree), or via `disconnect(a, b)`; no disband ceremony needed.

### Why this composes ("scales with more advanced processes")

| Advanced process | How the spine supports it |
|------------------|---------------------------|
| Streaming children | A sibling message to a child waiting on children wakes it via the *existing* `_inject_event` wait (`agent.py:1351`) — unchanged |
| Broadcast / group | `delegate(..., team=label)` = the runtime opens **all-pairs links** for that turn's labeled children (O(n²) macro over the same primitive) |
| Loop / cost control | Trivial per-link message counter; graduated warnings are a policy reading it (REQ-9/13) |
| MAC catalogue / adoption | The same link edge, reused as the discovery hook: "sibling X has artifact Y" |
| Charter + mechanical verify (G1) | A `verify` policy inspects *pointer targets* at settlement — no core changes |
| Arbitration (L2) | The founder already holds authority; `escalate(resolve_as=dispute)` routes to it — unchanged |
| Nested / recursive | Authorization ("parent of both") recurses unchanged — any node with children can open links among them |
| Resume / recovery | Links reference agent ids; a resumed child re-uses the live registry (no per-agent state to restore) |

### What this removes from the spec

- Team object, `TeamStatus` FSM, membership dict, charter object as *core*,
  workspace path-values-scoping, sanctions records as core. All become
  optional policy/surfaces on top of links.
- Enforcement shrinks to: link registry + an eligibility check in one place
  (converse path) + a counter. The rest is design intent, not mechanism.

### Comparison

| | Spine (MVP) | Spec (advanced layer) |
|---|---|---|
| New runtime state | `_links` set + per-pair counter | `Team`, `TeamCharter`, `TeamNorms`, `message_log`, `sanctions` |
| Authorization | one check: caller is parent of both | founder/member facets, team membership |
| Delivery | reuse `_inject_queue` | new `TeamMailbox` or reuse |
| Shared state | existing ArtifactStore/ResultStore + pointers | new scoped workspace dir |
| New files | `policies/links.py` (tiny) | `policies/team.py`, `policies/workspace.py`, `tools/team.py` |
| Time to value | hours | days |

Recommended structure: **build the spine; mount the advanced processes as policy
layers over it** (the codebase's own pattern — see `policies/verify.py`).
`collaboration-setting-spec.md` is demoted to the advanced layer: its AC-1..11
still hold, but as *policy-layer* acceptance on top of the spine.

---

## Scope comparison (quick read)

| Criterion | A parent-mediated | B sibling mailbox | C team/panel |
|-----------|-------------------|-------------------|--------------|
| Delivers "solve together" | Shallow | Fully | Partial |
| Respects context isolation | Yes | Group-scoped (bounded, authorized) | Partially |
| Scaling / parent bottleneck | **Fails** | Good | Medium |
| Parent context pressure | High (pollutes) | Low | Medium |
| Implementation size | — (rejected) | Medium–Large | Medium |
| Pick if | — | Collaboration is the product | You need shared-state teamwork with guardrails |

## Investigation next steps

- [x] Read `docs/concepts/delegation-model.md` + `self-healing.md` end-to-end
- [x] Decide the collaboration channel: workspace-primary, messages-as-exception
      (anchored in media-richness, boundary objects, blackboard, git practice)
- [x] Decide the facilitation layer: L0 pure peering + L1 mechanical
      facilitation (policy: monitoring/sanctions/provenance) + L2 sparse parent
      arbitration; no facilitator agent (anchored in Ostrom's commons governance)
- [x] Decision log: option A rejected (scaling + context pollution); B-curated
      group = common parent + explicit membership (Hackman); parent = context
      provider, never relay
- [x] Scope decision: founding is boundary-scoped (any parent at its layer),
      participation is universal (all agents, leaves included) — the
      "collaboration setting" object = Hackman's five conditions per layer,
      recurring down the tree (nested enterprises)
- [x] Written the collaboration-setting spec as a first-class construct →
      `collaboration-setting-spec.md` (object model, facets, lifecycle, rules,
      enforcement points, config, AC-1..11, non-goals, open items)
- [x] Simplicity review: distilled the arch to a spine — runtime `_links`
      (parent-of-both authorization) + reuse of converse/_inject_queue delivery
      + artifact/result pointers. Spec demoted to the advanced policy layer.
- [ ] Trace the exact `stream_children` event flow in `core/agent.py`
- [ ] Confirm sibling/push plumbing reuse (converse/continue_with_input/
      submit_input/_inject_queue) and what a new scope rule must gate
- [ ] Enumerate failure/steering cases (empty artifact, failed child, looping
      child, straggler) and map each to converse/resume/kill/re-delegate
- [ ] Spec the workspace mechanics: scoped `ArtifactStore` area + visibility +
      append/review conventions (the C-gap the theory does not settle)
- [ ] Spec round/cadence semantics: when a child "fetches newly-settled
      siblings'" writes (settle-then-yield reinterpreted for a shared surface)
- [ ] Define the equivocal-vs-uncertain heuristic so a child knows when to write
      vs message (bias workspace-first by default)
- [ ] Decide the `introduce` mechanism: delegation-time (`collaborate_with`) vs
      mid-run (`introduce` tool) vs both; define the signal-based decision rules
- [ ] Write the concrete target-behavior spec from REQ-1..12 + channel rules
- [ ] Flag the G1/G7 mechanism gap as a prerequisite or explicit non-goal
