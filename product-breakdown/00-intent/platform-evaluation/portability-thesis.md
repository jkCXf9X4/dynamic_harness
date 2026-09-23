---
title: "Portability Thesis"
category: meta
summary: >
  The five mechanically enforced mechanisms worth porting, and why they fit a
  host's tool-execution and spawn layer as a thin per-host adapter over a
  language-neutral core.
parent: "README.md"
---

# Portability Thesis

The claims worth porting are the mechanically enforced ones, because only they
survive model disobedience:

1. Repeated-call / near-identical loop detection (fuzzy signatures)
2. Result caching behind opaque read-only handles (`result_read`)
3. Blunt-vs-rot self-healing with a shared heal budget + the deliverable gate
4. Spawn limits at a single choke point, with target signatures
5. Checkpoint persistence + cross-restart resumability

All five live on a ~25-tool **tool-execution and spawn layer**, not in the
language runtime or model loop. That layer is exactly what a harness's extension
API exposes. A common shape recurs across the surveyed hosts:

- A **hook that can block or mutate a tool call before/after execution** (for
  loop detection, result caching, deliverable gating, token budgets)
- A **way to intercept agent spawning** (for spawn caps, parent/child model)
- **Persisted sessions** the host already maintains (for checkpoint replacement)

So the port is a thin adapter per host, wrapped around a language-neutral core of
the safety mechanisms.
