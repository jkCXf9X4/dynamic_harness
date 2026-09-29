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

<!-- pb:index:start -->
- **INFO-179** [Plugin Direction — Remaining Seams Breadth Audit + Trim](audit-other-seams.md) — Event bus, LLM provider, agent-class registry, data types, and the trimmed target.
- **INFO-180** [Plugin Direction — Policy-Seam Breadth Audit](audit-policies.md) — Consumers of each decision policy, and how the shared/domain split holds.
- **INFO-181** [Plugin Direction — Tool-Call Contract Breadth Audit](audit-tool-context.md) — Member-by-member consumers of ToolContext, the trimming rule, and the narrowing proposals.
- **INFO-182** [Plugin Direction — Context: How the References Build and Use It](context-architecture.md) — Context is the real test of plugin-centricity: who contributes to the model's context, in what order, with what scope, and how it is observed. OpenCode V2 and DeepSeek Harness both make context a contribution space, not a shared object; the harness's reactive-policy seam is the same shape — the gap is per-agent registration scoping.
- **INFO-183** [Plugin Direction — Decisions Q1–Q7](decisions.md) — The seven decisions from review of the initial draft.
- **INFO-184** [Plugin Direction — Compared Designs: OpenCode V2 and DeepSeek Harness](design-comparison.md) — The two reference plugin-centric architectures, mapped onto the ~7-interface target; what validates seam-first/no-loader, and the two lessons worth adopting (one registration contract, per-request tool snapshot).
- **INFO-185** [Plugin Direction — The Step Being Investigated](goal.md) — Establish and minimize the common interfaces between internal components and decouple/isolate them; plugin-ready structure, not plugin infrastructure.
- **INFO-186** [Plugin Direction — Current Interface Inventory](interface-inventory.md) — The seams that exist today and the observed couplings that make them incidental rather than minimal.
- **INFO-187** [Plugin Direction — Target Common-Interface Set (~7)](interface-set.md) — The seven interfaces that constitute the target; success means the count holds while couplings are removed.
- **INFO-188** [Plugin Direction — Motivating Context](motivation.md) — The seed suggestion, the reactive-policy reference model, and the purpose ruling: internal-structure enablement; external porting out of scope.
- **INFO-189** [Plugin Direction — Investigation Next Steps](next-steps.md) — The completed checklist that carried the direction from question to implemented pilot seam.
- **INFO-190** [Plugin Direction — Design Space / Options](options.md) — Three options weighed: loader (out of scope), seam-first refactor (recommended), two-worlds (out of scope here).
- **INFO-191** [Plugin Direction — Resolved Rulings 1–4](rulings.md) — ToolContext single+narrowed, policy-application split, no stdlib descriptor conversion, no discovery in tests.
- **INFO-192** [Plugin Direction — Success Criteria](success-criteria.md) — Six measurable criteria for the interface-economy direction.
- **INFO-193** [Plugin Direction — Target Definition](target.md) — Interface economy: a small, stable set of narrow contracts. Six properties.
<!-- pb:index:end -->

## Decisions

- AD-007 — Plugin Direction = Interface Economy (~7 Seams), No Loader / Late Injection
