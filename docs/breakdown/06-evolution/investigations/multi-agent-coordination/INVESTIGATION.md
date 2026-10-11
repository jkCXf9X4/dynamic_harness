---
id: INFO-148
type: info
title: "Direction: Complicated to Complex Multi-Agent Coordination"
summary: Direction work (pre-implementation) for moving from parallel decomposition to multi-agent coordination, where a parent stands up children that communicate and solve together. Option A (parent relaying) is rejected — see `AD-001`.
date: 2026-09-28
status: current
---

# Direction: Complicated to Complex Multi-Agent Coordination

## The step being investigated
From **complicated** development — decompose a problem into independent sub-parts
and solve them in isolation — to **complex** development — a parent stands up
multiple children that can *communicate* and *solve together*.

| Aspect | Complicated (default today) | Complex (target) |
|--------|------------------------------|------------------|
| Mechanism | `delegate` all-or-nothing batch gather | `agent.stream_children: true` + `converse` + `[child settled]` events |
| Children | Isolated leaves, run to completion | Fire-and-forget, live, steerable mid-flight |
| Parent role | Fan-out, then wait, then gather, then verify, then synthesize | Reactive orchestrator: converse, re-delegate, kill stragglers, report early |
| Communication | Child to parent only, via artifacts, at the end | Bidirectional parent and child, mid-flight |

## What already exists (implemented)
- `agent.stream_children` (config, default false) — `config.py:265`
- Streaming `[child settled]` injection — `core/agent.py:1374`, `:1410`, `:1461`
- `converse` tool (nudge a live child) — `core/tools/agents.py:306`
- `kill` / `status` / `resume` tools for parent-side steering
- Self-heal layers documented — self-healing concept

## Key open questions
See `INFO-171` — scope of "solve together",
cost/context floor, verification as mechanism, failure steering, termination.

## Design conclusions (canonical leaves)
- `INFO-175` — the A/B/C design space; option A rejected.
- `INFO-176` — B-curated: common-parent scoping, mechanism, patterns.
- `INFO-177` — mitigations of B's cons + residual concerns.
- `INFO-173` — REQ-1..7 (group, context, norms).
- `INFO-174` — REQ-8..15 (steering, safety, commons).
- `INFO-161` — parent introduces, never relays; signals not content.
- `INFO-162` — risks/convergence of the introduce model.
- `INFO-150` — workspace-primary, messages-as-exception.
- `INFO-151` — the theory anchors behind the channel decision.
- `INFO-160` — L0/L1/L2, no facilitator agent.
- `INFO-172` — commons-governance evidence.
- `INFO-149` — founding boundary-scoped, participation universal.
- `INFO-159` — Hackman's five conditions per layer + facets.
- `INFO-178` — the three-primitive spine; spec demoted to the advanced layer.

## Investigation next steps (open)
- Trace the exact `stream_children` event flow in `core/agent.py`
- Confirm sibling/push plumbing reuse (converse/continue_with_input/submit_input/_inject_queue) and what a new scope rule must gate
- Enumerate failure/steering cases (empty artifact, failed child, looping child, straggler) and map each to converse/resume/kill/re-delegate
- Spec the workspace mechanics: scoped `ArtifactStore` area + visibility + append/review conventions
- Spec round/cadence semantics: when a child fetches newly-settled siblings' writes
- Define the equivocal-vs-uncertain heuristic so a child knows when to write vs message
- Decide the `introduce` mechanism: delegation-time (`collaborate_with`) vs mid-run (`introduce`) vs both
- Write the concrete target-behavior spec from REQ-1..12 + channel rules
- Flag the G1/G7 mechanism gap as a prerequisite or explicit non-goal
