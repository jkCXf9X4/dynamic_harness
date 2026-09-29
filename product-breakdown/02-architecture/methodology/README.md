---
title: Agent Methodology
summary: The guidelines governing how every agent decomposes, delegates, verifies, synthesizes, and terminates. Derived from VISION.md and the agent system pro…
---

# Agent Methodology

The guidelines governing how every agent decomposes, delegates, verifies,
synthesizes, and terminates. Derived from [VISION.md](../../00-intent/VISION.md)
and the agent system prompt; all principles follow ISO/IEC 15288 systems
engineering.

## Owns
- Core philosophy and the golden delegation rule
- The 15288 lifecycle mapping and mandatory workflow
- The priority hierarchy (P0–P8), verification protocol, reporting format
- Failure recovery, cost heuristics, and guardrails

## Excludes
- Concept detail → [../concepts/](../concepts/)
- Worked examples → [../examples/](../examples/)
- Decision records → [../decisions/](../decisions/)

See [../examples/anti_patterns.md](../examples/anti_patterns.md) for the nine

anti-patterns, plus the delegation-description, execution-pattern, and

task-framing examples in [../examples/](../examples/).

## Contents

<!-- pb:index:start -->
- **INFO-056** [Delegation Quality (P6, P8)](delegation-quality.md) — A sub-agent's description + role is its entire world (its allocated requirements)
- **INFO-057** [Core Philosophy](philosophy.md) — Maximize output quality while minimizing cost through disciplined task decomposition, strict context encapsulation, and a mandatory analyze → implemen…
- **INFO-058** [Priority Hierarchy](priorities.md) — Output decomposition plan before any tool call. Skipping this and jumping to glob/grep is the 1 cause of context bloat
- **INFO-059** [Failure Recovery & Cost](recovery-and-cost.md) — See delegation-guidelines skill → "The Kill → Inspect → Retry loop" for the full salvage-and-retry protocol. Short version
- **INFO-060** [Report Format](reporting.md) — Report Format
- **INFO-061** [Verification Protocol](verification.md) — For each child after returns
- **INFO-062** [Mandatory Workflow](workflow.md) — Mandatory Workflow
<!-- pb:index:end -->
