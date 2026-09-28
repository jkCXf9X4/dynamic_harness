---
title: "Investigation — Complicated → Complex: Multi-Agent Coordination"
category: investigation
status: open
summary: >
  Direction work (before implementation) for moving from parallel decomposition
  (problems broken into independent sub-parts) toward multi-agent coordination
  where a parent stands up several children that communicate and solve problems
  together. Parent-mediated relaying (option A) is rejected — see the decision log
  (../../decision-log.md, DL-*) and AD-001 (../decisions/AD-001.md). Conclusions
  and design live in the sibling leaves listed below.
---

# Direction: Complicated → Complex Multi-Agent Coordination

## The step being investigated
From **complicated** development — decompose a problem into independent sub-parts
and solve them in isolation — to **complex** development — a parent stands up
multiple children that can *communicate* and *solve together*.

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
- Self-heal layers documented — `../concepts/self-healing/README.md`

## Key open questions
See [open-questions.md](open-questions.md) — scope of "solve together",
cost/context floor, verification as mechanism, failure steering, termination.

## Design conclusions (canonical leaves)
- [scope-options.md](scope-options.md) — the A/B/C design space; option A rejected.
- [sibling-collaboration.md](sibling-collaboration.md) — B-curated: common-parent scoping, mechanism, patterns.
- [sibling-scoping.md](sibling-scoping.md) — mitigations of B's cons + residual concerns.
- [requirements-group.md](requirements-group.md) — REQ-1..7 (group, context, norms).
- [requirements-steering.md](requirements-steering.md) — REQ-8..15 (steering, safety, commons).
- [introduce-not-mediate.md](introduce-not-mediate.md) — parent introduces, never relays; signals not content.
- [introduce-risks.md](introduce-risks.md) — risks/convergence of the introduce model.
- [channel-decision.md](channel-decision.md) — workspace-primary, messages-as-exception.
- [channel-evidence.md](channel-evidence.md) — the theory anchors behind the channel decision.
- [facilitation-layer.md](facilitation-layer.md) — L0/L1/L2, no facilitator agent.
- [ostrom-principles.md](ostrom-principles.md) — commons-governance evidence.
- [capability-scope.md](capability-scope.md) — founding boundary-scoped, participation universal.
- [collaboration-setting-model.md](collaboration-setting-model.md) — Hackman's conditions per layer + facets.
- [spine.md](spine.md) — the three-primitive spine; spec demoted to the advanced layer.

## Investigation next steps
- [x] Read `../concepts/delegation-model/README.md` + `../concepts/self-healing/README.md` end-to-end
- [x] Decide the collaboration channel: workspace-primary, messages-as-exception
- [x] Decide the facilitation layer: L0 pure peering + L1 mechanical + L2 sparse parent arbitration; no facilitator agent
- [x] Decision log: option A rejected (scaling + context pollution); B-curated group = common parent + explicit membership; parent = context provider, never relay
- [x] Scope decision: founding boundary-scoped, participation universal; setting = Hackman's five conditions per layer
- [x] Written the collaboration-setting spec → [collaboration-setting/](collaboration-setting/)
- [x] Simplicity review: distilled the arch to a spine — runtime `_links` + reuse of converse/_inject_queue delivery + pointers; spec demoted
- [ ] Trace the exact `stream_children` event flow in `core/agent.py`
- [ ] Confirm sibling/push plumbing reuse (converse/continue_with_input/submit_input/_inject_queue) and what a new scope rule must gate
- [ ] Enumerate failure/steering cases (empty artifact, failed child, looping child, straggler) and map each to converse/resume/kill/re-delegate
- [ ] Spec the workspace mechanics: scoped `ArtifactStore` area + visibility + append/review conventions
- [ ] Spec round/cadence semantics: when a child fetches newly-settled siblings' writes
- [ ] Define the equivocal-vs-uncertain heuristic so a child knows when to write vs message
- [ ] Decide the `introduce` mechanism: delegation-time (`collaborate_with`) vs mid-run (`introduce`) vs both
- [ ] Write the concrete target-behavior spec from REQ-1..12 + channel rules
- [ ] Flag the G1/G7 mechanism gap as a prerequisite or explicit non-goal
