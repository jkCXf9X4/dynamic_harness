---
title: "Plugin Direction — Target Definition"
category: investigation
parent: "README.md"
summary: >
  Interface economy: a small, stable set of narrow contracts. Six properties.
---

# The target (working definition)

Not a plugin manifest/activation lifecycle. The target is **interface
economy** — a small, stable set of narrow contracts, with these properties:

1. **Few.** One contract per *kind* of exchange (observe-and-react, tool call,
   delegate, deliver report, persist state, generate) — not one per feature.
2. **Narrow.** Each interface exposes exactly what its consumers need; nothing
   private leaks through; no full-object handoffs where a view suffices.
3. **Stable.** The contracts hold across refactors; components change behind
   them, interfaces change rarely.
4. **Host-agnostic where possible.** Decisions (`core/policies/`) import
   neither agent nor runtime; data types (`Task`, `Artifact`, `Commit`,
   `Observation`, `PromptInjection`) are pure. Mirrors the reactive-policy
   reference model.
5. **Isolated.** Components know neighbors only through contracts; internals
   (agent context buffers, registry internals, store layouts) are private.
6. **Replaceable as a side effect.** Narrow seams + explicit
   register/inject points make swapping a tool, policy, handler, or provider a
   one-call act — without a loader, without monkey-patching.
