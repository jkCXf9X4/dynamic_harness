---
title: Layer 00 — Intent
summary: Why does the project exist, who is it for?
---

# Layer 00 — Intent

**Why does the project exist, who is it for?**

Dynamic Harness is a recursive agent runtime that exists to maximize LLM output quality while minimizing cost — by enforcing disciplined task decomposition, strict context encapsulation, and a mandatory analyze → implement → verify loop inspired by ISO/IEC 15288 systems engineering. It is for developers and tool-builders who run multi-step, tool-calling agent workloads (repository analysis, change-and-validation, research-and-synthesis, pipelines-and-jobs, evaluation-and-qa, embedding-and-integration) and want deterministic safety/recovery machinery that works even when the model ignores instructions — rather than prompt advice.

This layer is the "why". It holds the founding thesis (fresh context is cheaper than accumulated context), the vision, and the differentiation story — not the deliverables, design, or scripts. The platform-evaluation position lives under `06-evolution/investigations/platform-evaluation/`.

## Owns
- Motivation, stakeholders, research questions, outcomes
- Constraints and assumptions (e.g. no shared-memory system, no code generation, no chatbot framework)
- Vision statement, success criteria, cost model
- Competitive differentiation and platform/portability position

## Excludes
- Deliverables, capabilities, use cases → `01-product/`
- Design, architecture, components → `02-architecture/`
- Scripts, interfaces, configs → `03-implementation/`
- Tests, proof criteria → `04-verification/`
- Release, runbook → `05-operation/`
- Backlog, roadmap → `06-evolution/`

## Contents

<!-- pb:index:start -->
- [Competitive Differentiation](competitive-differentiation/README.md) — What separates Dynamic Harness from other agent harnesses (CrewAI, LangGraph, AutoGen, OpenAI Agents SDK, Claude Code, MCP-based tools): the mechanically-enforced guarantees that survive model disobedience, separated from prompt-level advice shared with the field.
- **INFO-001** [VISION](VISION.md) — Dynamic Harness is a recursive agent runtime that maximizes LLM output quality while minimizing cost — by enforcing disciplined task decomposition, st…
<!-- pb:index:end -->
