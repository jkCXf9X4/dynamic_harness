---
title: "Competitive Differentiation"
category: meta
summary: >
  What separates Dynamic Harness from other agent harnesses (CrewAI, LangGraph,
  AutoGen, OpenAI Agents SDK, Claude Code, MCP-based tools): the
  mechanically-enforced guarantees that survive model disobedience, separated
  from prompt-level advice shared with the field.
related:
  - ../VISION.md
  - ../../02-architecture/concepts/self-healing.md
  - ../../02-architecture/concepts/agent-lifecycle.md
  - ../../02-architecture/concepts/delegation-model.md
  - ../../04-verification/gap-analysis/README.md
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
context"** ([VISION](../VISION.md)). Most harnesses share surface features
(recursive delegation, tool-calling loops, context management) but not the
deterministic enforcement below.

Related: [platform-evaluation](../platform-evaluation/README.md),

[gap-analysis](../../04-verification/gap-analysis/README.md).

## Contents
