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

## Contents

- [goal.md](goal.md) — the structural goal and today-vs-target table.
- [motivation.md](motivation.md) — seed suggestion, reference model, purpose (Q1).
- [interface-inventory.md](interface-inventory.md) — seams today + observed couplings.
- [target.md](target.md) — the interface-economy properties.
- [options.md](options.md) — loader / seam-first / two-worlds.
- [decisions.md](decisions.md) — Q1–Q7.
- [rulings.md](rulings.md) — rulings 1–4 (ToolContext, policy path, stdlib, tests).
- [interface-set.md](interface-set.md) — the ~7 target common interfaces.
- [audit-tool-context.md](audit-tool-context.md) — ToolContext member→consumer audit.
- [audit-policies.md](audit-policies.md) — policy-seam consumers.
- [audit-other-seams.md](audit-other-seams.md) — event bus, LLM, registry, data types.
- [next-steps.md](next-steps.md) — investigation progress checklist.
- [success-criteria.md](success-criteria.md) — measurement criteria.

Decisions: [AD-007](../../../02-architecture/decisions/AD-007.md); DL-8, DL-9.
