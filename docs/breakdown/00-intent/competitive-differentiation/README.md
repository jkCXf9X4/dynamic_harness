---
title: "Competitive Differentiation"
summary: >
  What separates Dynamic Harness from other agent harnesses (CrewAI, LangGraph,
  AutoGen, OpenAI Agents SDK, Claude Code, MCP-based tools): the
  mechanically-enforced guarantees that survive model disobedience, separated
  from prompt-level advice shared with the field.
---

# Competitive Differentiation

Grounded comparison of Dynamic Harness against the mainstream agent harnesses.
It separates two things, always asking *"if the model disobeys the prompt, what
breaks?"*:

- **Mechanically enforced guarantees** — behavior enforced by deterministic
  runtime code, not prompt text. These are the genuine differentiators.
- **Prompt-level advice** — shared with the field; documented as guidance, not a
  differentiator.

Ground truth: the founding thesis is **"fresh context is cheaper than accumulated
context"** (`INFO-001`). Most harnesses share surface features
(recursive delegation, tool-calling loops, context management) but not the
deterministic enforcement below.

## Owns
- The competitive differentiation story: mechanically enforced guarantees vs prompt-level advice shared with the field
- The enforced/distinctive scoreboard and the defensible "only-us" positioning

## Excludes
- The founding thesis and vision: `INFO-001`
- Platform/portability position: `06-evolution/investigations/platform-evaluation/`
- Gap analysis: `04-verification/gap-analysis/`

## Contents

<!-- pb:index:start -->
<!-- GENERATED FILE — do not edit. Regenerate with pb-registers. -->
- **INFO-002** [Deterministic Safety — Loop Detection and Spawn Limits](deterministic-safety.md) — The runtime-enforced mechanisms that keep a disobedient model bounded: repeated-call / fuzzy near-identical loop detection, and per-lineage spawn caps keyed on target signatures.
- **INFO-003** [Gaps and Positioning](gaps-and-positioning.md) — The two pillars where enforcement is not yet mechanized (verification G1, budgeting G8), the enforced/distinctive scoreboard, and the defensible "only-us" positioning.
- **INFO-004** [Prompt-Level — Shared with the Field](prompt-level.md) — Design intent real in this codebase but not a mechanical guarantee — role allow-lists, context tools, progressive disclosure, provenance, streaming children, CLI composability — hence equivalent to what other harnesses offer.
- **INFO-005** [Result Handles — Caching Behind Opaque Read-Only Handles](result-handles.md) — Every cacheable tool call stores its full output behind an opaque handle; result_read pages it and result_bash pipes it to a shell's stdin, never re-executing the producing tool.
- **INFO-006** [Self-Healing and Resume](self-healing-and-resume.md) — Blunt-vs-rot diagnosis-driven recovery with a shared heal budget and a deliverable gate, plus checkpoint persistence that makes an interrupted run reconstructable across restarts.
<!-- pb:index:end -->
