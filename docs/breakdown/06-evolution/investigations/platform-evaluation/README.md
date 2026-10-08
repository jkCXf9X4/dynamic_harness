---
title: "Platform Evaluation: Porting the Harness Elsewhere"
category: meta
summary: >
  Feasibility assessment for re-implementing Dynamic Harness' mechanically
  enforced guarantees as add-ons on top of an existing agent platform (OpenCode,
  Pi, DeepSeek Harness) instead of building tools and scaffolding from scratch,
  grounded in each platform's documented extension API as of 2026-09.
related:
  - ../competitive-differentiation/README.md
  - ../../02-architecture/concepts/self-healing.md
  - ../../02-architecture/concepts/delegation-model.md
  - ../../04-verification/gap-analysis/README.md
---

# Platform Evaluation

Can Dynamic Harness' genuinely distinct claims be carried onto a third-party
agent host as **add-ons**, returning the commodity scaffolding (tool wiring,
session persistence, memory addons, RAG pipelines) to the host's ecosystem?

Framing follows [competitive differentiation](../competitive-differentiation/README.md):
only the **mechanically enforced** claims are worth porting, because those are
what survive model disobedience. Everything else (progressive disclosure,
provenance, fresh-context economics) is either prompt-level or provided by the
host.

Related: [gap-analysis](../../04-verification/gap-analysis/README.md).

## Contents
