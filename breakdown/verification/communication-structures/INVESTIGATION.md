---
title: "Investigation — How Communication Structures Influence Agent Success"
category: investigation
status: open
summary: >
  Empirical comparison of four communication topologies — parent-mediated,
  sibling-of-common-parent, one shared channel, and topic channels — measuring
  how each affects agent success (completion, quality, cost, context health) on
  a fixed collaboration task. Verification work: define the comparison bed and
  run it before any single structure is built out further.
---

# Investigation: Communication structures vs agent success

## The step being investigated

This is a **measurement-first** item under verification: before committing to
any one collaboration mechanism (see
`breakdown/development/multi-agent-coordination/`), establish *how different
communication structures influence how agents succeed at their work* — the same
task, the same tree shape, only the communication topology varying.

Structures to compare:

| # | Structure | One-line description |
|---|-----------|----------------------|
| 1 | **Parent-mediated** | Every exchange passes through the parent (relay) |
| 2 | **Same-parent siblings** | Children of one parent may message each other directly |
| 3 | **One shared channel** | All nodes read/write a single dedicated channel |
| 4 | **Topic channels** | Any node can register/create named channels by topic |

These four are not arbitrary modes — they form a recognisable lattice:

- **1 ⊂ 2** — a parent relaying between two children is sibling communication
  with the parent in the middle of the edge.
- **2 ⊂ 3** — same-parent scoping is the shared channel restricted to one
  subtree.
- **3 ⊂ 4** — one global channel is the degenerate case of topic channels (one
  topic, no filtering).

So the real question is: **where is the routing decision made** (parent,
sibling-scope, global, or topic-tagged) and what does that cost or earn?

## What already exists (concrete hooks in this codebase) — verified 2026-09-17

Ground-truth audit of the current seams (correcting an earlier draft that
assumed a ``_links`` spine and a sibling gate already existed — they do not):

| # | Structure | Current reality | Real moving part to change |
|---|-----------|-----------------|----------------------------|
| 1 | Parent-mediated | **Not the default.** `converse` is a global by-ID RPC (`runtime.get_agent` lookup, `core/agent.py:1708` → `runtime.py:1043`), gated only by target status (`ToolPermissionPolicy.conversable`, `core/policies/permissions.py:51`). A parent only "relays" if the model happens to forward a message. The pieces for a relay exist (`stream_children` + `[child settled]` folding, `_format_delegate_result` `core/agent.py:985`) | Add a backend that routes any non-parent-peer message to the common parent instead of the named peer |
| 2 | Same-parent siblings | **Gate does not exist.** `converse` currently reaches *any* agent, including across unrelated subtrees; nothing enforces `caller.parent is a.parent and caller.parent is b.parent` | Add a backend that restricts the by-ID `message`/`converse` target to same-parent peers |
| 3 | One shared channel | **Partial.** There is no runtime mailbox, but the delivery primitives exist: `submit_input`/`_inject_event` mid-run injection (`core/agent.py:1428/246`), tail-append via `_drain_inject_input` (`core/agent.py:1440`), and the broadcast-shaped `EventBus` (`core/events.py`) | One append-only log (per-subscriber watermark) in the runtime; read via a new cacheable tool, push via the digest policy |
| 4 | Topic channels | **De facto shape, but implicit.** Agents emulate channels by writing scoped artifacts + `converse` pushes; nothing *routes* — there is no topic registry, no subscription, no per-agent delta | A `topic → {subscribers, artifact area}` registry + `join`/`post`/`read` tools; routing authority via a `ChannelPolicy` |

**The corrected baseline:** today there is exactly *one* router — any-agent
by-ID, blocking request/response. That is cell 2/3-ish reachability with none
of the containment. The experiment therefore cannot run by toggling existing
gates (there are none); it needs a thin, *explicit* routing layer whose only
job is to make "who routes what" a swappable decision. The plan for that layer
is in `PLAN.md` in this directory.

## What "agents succeed at their work" means — measurable

Agree a success battery up front so the comparison is fair. Proposed axes
(measurable from existing telemetry/usage/artifacts):

1. **Completion** — final task status (completed / escalated / failed) on the
   same task set. Natural outcome per trial.
2. **Quality** — VERIFY outcome / acceptance-criteria pass (gap G1). Needs a
   mechanical checker on the deliverable, not prompt-discipline.
3. **Cost** — total tokens (`Runtime.total_usage()`), LLM calls, wall-clock.
4. **Context health** — peak and final message-count / estimated-token
   footprint per agent (from the `usage` tool). Proxy for "did the topology
   rot contexts".
5. **Contention / accident rate** — cycle detections (repeated-call),
   conflicting writes, kills, self-heal activations. Social topologies (3, 4)
   are expected to pay here; measure it.

### Controlled comparison bed

Everything constant except the topology: fixed tree (one parent, 4 children),
fixed task (one deliverable that requires shared intermediate findings — the
*interdependent* case, not independent fan-out), same LLM provider and model,
same budgets, N replicates per cell.

| Structure | Predicted strength | Predicted weakness |
|-----------|--------------------|--------------------|
| 1 Parent-mediated | Simplest, deterministic, no unvetted edges; parent guarantees the deliverable | Parent context rot; latency serializes parallel work; relay bottleneck |
| 2 Same-parent siblings | Direct handoff, low parent context pressure; bounded edge set; parent stays authority | Isolation softened for the group; needs per-pair cycle caps |
| 3 One shared channel | Maximal information flow; no routing search cost | Inbox flood; unbounded contamination; commons-tragedy needs a broker anyway |
| 4 Topic channels | Information routed where needed; artifacts give provenance; the current de facto shape | Channel naming/granularity decisions; stale-topic drift; routing is still a model decision |

## Key open questions

1. **What is the natural comparison unit?** One run yields an outcome, but
   success is noisy. Replicate count / variance budget must be set before
   calling a loser on noise.
2. **Is "richer channel = better" the right hypothesis?** Media-richness theory
   predicts *matching* the medium to the task (lean work → shared store; equivocal
   → rich messages), not "more channel always wins". Score per-task
   equivocaity, not an overall average.
3. **Does structure change *who succeeds* or only *what it costs*?** On easy
   tasks all topologies may complete; differences should show on a task
   gradient (easy → hard collaboration). Need that gradient in the bed.
4. **What role does the parent play per structure?** In 1 a router; in 2/4 an
   authority at the boundary; in 3 nobody. Is "no authority" survivable
   (Ostrom: long-lived commons have institutions)?
5. **Can 3 even run as designed** without instantly tripping the
   repeated-call / context guards? If the safety invariants make cell 3
   untestable, that is itself a result.

## Investigation next steps

> Implementation plan and tool-surface design: see `PLAN.md` in this directory.
> The first three steps below are the plan's P0–P3 phases.

- [ ] Write the success-battery definition (5 axes above, operationalized)
- [ ] Define the task gradient (independent → interdependent → adversarial)
      and reuse `benchmark/tasks.py` infrastructure where possible
- [ ] Implement the 4 topologies as thin switches on the existing links /
      mailbox / artifact seams: 1 = existing relay; 2 = `_links` gate; 3 = one
      global mailbox; 4 = topic registry over artifact stores
- [ ] Run the controlled comparison (deterministic mock-LLM first for
      correctness, then real-LLM probes with N replicates per cell)
- [ ] Report completion / quality / cost / context-health / contention per cell
- [ ] Decide which structure(s) feed the collaboration spine
      (`breakdown/development/multi-agent-coordination/`), or confirm the
      current hybrid (4 de facto)

## Success criteria

1. The bed is reproducible — mock-LLM runs give the same cell ranking;
   real-LLM spread is reported as variance, not asserted away.
2. All four topologies run on the same task/tree/budget set, with no safety
   exemptions granted to cell 3.
3. The report answers "does richer communication change *completion/quality*
   or only *cost*?" with numbers.
4. A topology (or the hybrid) is adopted on evidence, not on the dev
   investigation's design reasoning alone.