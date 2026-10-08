---
id: INFO-158
type: info
title: Collaboration Setting — Purpose and Scope
summary: "Section 1 of the collaboration-setting spec. Index: README.md"
date: 2026-09-28
status: current
---

# Collaboration Setting — Purpose and Scope

Section 1 of the collaboration-setting spec. Index: `collaboration-setting`.

This spec defines the **team** (the "collaboration setting"): the first-class
runtime construct a founding parent instantiates at its delegation boundary so
that interdependent children can collaborate — share findings, negotiate,
arbitrate — *without* relaying through the parent (option A, rejected).

- **Distributed capability.** Every `Agent` node carries the same
  `CollaborationCapability` with two facets: MEMBER (active iff introduced) and
  FOUNDER (active iff the node has children). Activation is structural.
- **Layer-by-layer.** A team is instantiated at any delegation boundary where
  the parent declares interdependent children. A member child that later
  delegates founds its own nested team (Ostrom #8). Same object class at every
  layer (Hackman: real team + compelling direction are the core, provided per
  layer by that layer's father).
- **Tracing.** Each requirement maps to `INFO-173`
  / `INFO-174` REQ-1..15 and
  `INFO-168` §7.
