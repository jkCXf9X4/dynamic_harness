---
title: "Prompt-Level — Shared with the Field"
category: meta
summary: >
  Design intent real in this codebase but not a mechanical guarantee — role
  allow-lists, context tools, progressive disclosure, provenance, streaming
  children, CLI composability — hence equivalent to what other harnesses offer.
parent: "README.md"
related:
  - ../../02-architecture/concepts/delegation-model.md
---

# Prompt-Level — Shared with the Field

Design intent that is real *in this codebase* but not a mechanical guarantee, and
therefore equivalent to what other harnesses offer at the API level:

- **Role-scoped tool allow-lists** — enforced in code (`tools/registry.py`;
  orchestrators can't do hands-on work). Stronger than most, but "roles" as a
  concept exists elsewhere.
- **Prune / restore / compress context tools** — implemented (`core/context.py`).
  Standard context-management surface.
- **Progressive disclosure (headline → raw)** — implemented (`artifact/store.py`).
  Unusual degree, but the idea exists in artifact layers everywhere.
- **Git-like provenance (commits, parents, children)** — implemented
  (`memory/repository.py`). Shared with versioned-artifact systems.
- **Streaming children (fire-and-forget, event-driven parent reactions)** —
  implemented (`agent.stream_children`). A divergence, not a default; see below.
- **Unix-composability (CLI files, not dashboards)** — implemented (`cli/`).
  Design choice, not a capability gap.

## Streaming children — a divergence, not a default

By default delegation is all-or-nothing: a parent that delegates several children
blocks until *every* child settles. With `agent.stream_children: true` children
are fire-and-forget and the parent is re-admitted to its loop as each child
settles (`[child settled]` injected), letting it react to one child before
siblings finish — re-delegate a failed branch, cancel stragglers, or report
early. The cost trade-off is documented in
[delegation-model](../../02-architecture/concepts/delegation-model.md).
