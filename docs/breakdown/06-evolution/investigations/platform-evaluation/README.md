---
title: "Platform Evaluation: Porting the Harness Elsewhere"
summary: >
  Feasibility assessment for re-implementing Dynamic Harness' mechanically
  enforced guarantees as add-ons on top of an existing agent platform (OpenCode,
  Pi, DeepSeek Harness) instead of building tools and scaffolding from scratch,
  grounded in each platform's documented extension API as of 2026-09.
---

# Platform Evaluation: Porting the Harness Elsewhere

Can Dynamic Harness' distinct claims be carried onto a third-party agent host
as **add-ons**? The commodity scaffolding (tool wiring, session persistence,
memory addons, RAG pipelines) returns to the host's ecosystem.

Framing follows the competitive differentiation index: only the
**mechanically enforced** claims are worth porting. Those survive model
disobedience. Everything else (progressive disclosure, provenance,
fresh-context economics) is prompt-level or host-provided.

Related: gap analysis index.

## Chain status

- **Question** — present, in this index.
- **Plan** — present, in `INFO-011`.
- **Findings** — present, in `INFO-007`, `INFO-008`, `INFO-009`, `INFO-010`.
- **Results** — present, in `INFO-012`.

## Contents

<!-- pb:index:start -->
<!-- GENERATED FILE — do not edit. Regenerate with pb-registers. -->
- **INFO-007** [Host — DeepSeek Harness (dsh)](deepseek-harness.md) — DeepSeek Harness is the closest philosophical twin — native subagents, goals domain, spill store and token meter — but a dev preview with a nascent ecosystem, and loop safety remains yours to build.
- **INFO-008** [Fit Against the Five Mechanisms](fit-matrix.md) — Each portability mechanism mapped onto OpenCode, Pi, and DeepSeek Harness: what is native, what needs a hook, and what is effectively absent.
- **INFO-009** [Host — OpenCode](opencode.md) — OpenCode (anomalyco/opencode) is mature with native subagents and sessions; tool-level guarantees fit a Python MCP server and loop-level guarantees a thin TS plugin.
- **INFO-010** [Host — Pi](pi.md) — Pi (earendil-works/pi-mono) has the friendliest extension API but no in-tree subagents or permission controls, so the delegation moat returns as process-spawned subagents with no in-process task graph.
- **INFO-011** [Portability Thesis](portability-thesis.md) — The five mechanically enforced mechanisms worth porting, and why they fit a host's tool-execution and spawn layer as a thin per-host adapter over a language-neutral core.
- **INFO-012** [Verdict and Recommendation](verdict-and-recommendation.md) — Pi is the wrong substrate, DeepSeek Harness is the closest philosophical twin but fails the ecosystem motivation, and OpenCode is the pragmatic pick — commit the architecture, not the vendor.
<!-- pb:index:end -->
