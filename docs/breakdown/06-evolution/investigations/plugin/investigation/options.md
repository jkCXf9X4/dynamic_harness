---
id: INFO-190
type: info
title: "Plugin Direction — Design Space / Options"
summary: >
  Three options weighed: loader (out of scope), seam-first refactor
  (recommended), two-worlds (out of scope here).
date: 2026-09-28
status: current
---

# Plugin Direction — Design Space / Options

## A. Loader / late-injection plugin architecture — OUT OF SCOPE

No manifest schema, no directory scanning, no entry points, no activate/
deactivate lifecycle, no dynamic code loading. The user decided this is *not
needed*: the goal is structural, and a loader is machinery that buys nothing
until the seams are already minimal. Folded away so future work does not
re-litigate it. (If contracts do prove stable much later, a loader could sit
on top — but that is the platform-evaluation investigation's territory
(`INFO-012`), not this item.)

## B. Seam-first refactor (the recommended path)

Do the interface work only, in the codebase's natural order: inventory, then
narrow, then isolate, then consolidate registries. No new I/O, no new failure modes.

**Pros:** low risk; every change is a refactor with existing tests as the
guard (`pytest` mock-LLM determinism preserved); the reactive-policy refactor
already proved the pattern; produces the plugin-ready structure directly.
**Cons:** slower to see a "capability" land; requires discipline to avoid
churning interfaces for their own sake (explicit non-goal: reshuffling without
coupling reduction).

## C. Two-worlds (internal seams + external transport) — OUT OF SCOPE here

Serving the decision layer behind an MCP/third-party-host transport belongs to
the platform-evaluation investigation (`INFO-012`). This item only makes the codebase portable;
it does not ship a transport. (Enablement: B enables C later.)
