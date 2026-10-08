---
title: "Investigation — Interface Economy: Decoupling Toward a Plugin-Ready Structure"
category: investigation
status: open
summary: >
  Direction work for making Dynamic Harness' internals decoupled and isolated:
  a minimal set of narrow, stable common interfaces between components, so the
  structure is plugin-ready (seams first) without a plugin architecture or
  late code injection.
---

# Interface Economy: Decoupling Toward a Plugin-Ready Structure

Investigation of a **structural goal**: establish and **minimize** the common
interfaces between internal components, and decouple/isolate them behind those
interfaces. Plugin-ready *structure* is the target; a loader is out of scope.

## Owns
- The interface-economy direction, its motivating context, the seam inventory, the ~7-interface target set, rulings, options, next steps, and success criteria.

## Excludes
- Runtime-coupled API docs → `../../../../docs/api/`; external porting / MCP transport → `../../../00-intent/platform-evaluation.md`.

Decisions: [AD-007](../../../../decisions/AD-007-plugin-direction-interface-economy-7-seams-no-loader-late-injection.md); DL-8, DL-9.

## Contents

## Decisions

- AD-007 — Plugin Direction = Interface Economy (~7 Seams), No Loader / Late Injection
