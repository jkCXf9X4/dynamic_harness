---
id: INFO-188
type: info
title: "Plugin Direction — Motivating Context"
category: investigation
parent: "README.md"
summary: >
  The seed suggestion, the reactive-policy reference model, and the purpose
  ruling: internal-structure enablement; external porting out of scope.
date: 2026-09-28
status: current
---

# Why this matters (motivating context)

The seed suggestion (from `product-breakdown/06-evolution/06-evolution/backlog.md`):

> Most policies react to some metric and inject or alter the prompt in some
> way — can you see if you can create a common interface for these to further
> facilitate the move towards a more plugin centric architecture.

`ReactivePolicyRegistry` (`core/policies/interface.py`) answered that for the
*metric-reactive* family — it is the reference for what a good seam looks like:
host-agnostic, narrow, stable. `../../../00-intent/platform-evaluation.md` argues
the core worth porting is a ~25-tool tool-execution + spawn layer, reusing
policies without coupling.

**Purpose decision (Q1 answered):** this work is *porting and adaptation of the
current project structure into a more decoupled and manageable codebase* — the
internal-structure enabler. External porting (MCP server / third-party host
transport) belongs to `../../../00-intent/platform-evaluation.md` and is **out of
scope here**.