---
title: "Plugin Direction — Decisions Q1–Q7"
category: investigation
parent: "README.md"
summary: >
  The seven decisions from review of the initial draft.
---

# Decisions (from review of the initial draft)

- **Q1 — Purpose:** porting/adaptation of the current project structure into a
  more decoupled and manageable codebase; external porting is out of scope.
- **Q2 — Manifest schema (if ever considered):** minimal (name/version/
  contributions); moot under "no loader".
- **Q3 — Failure/containment:** **crash loudly and warn in the terminal** —
  never silently swallow a broken component/registration.
- **Q4 — Safety boundary:** go with the default bias: policies replaceable,
  safety invariants frozen (loop detection, spawn limits, result handles,
  mutator set), tools additive, agent classes additive.
- **Q5 — Config interplay:** **start code-only**; components consume
  `harness.json` exactly as today, no merged per-component schema.
- **Q6 — Stdlib conversion:** NOT a prerequisite — defaults are registered
  through the same public register calls as anything else; no descriptor
  conversion. (Resolved ruling, [rulings.md](rulings.md) ¶3.)
- **Q7 — Deterministic testing:** no discovery, ever — component lists are
  explicit or default, never scanned. (Resolved ruling, [rulings.md](rulings.md) ¶4.)
