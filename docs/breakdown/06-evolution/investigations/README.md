---
title: Investigations
summary: Design-space investigations feeding the roadmap register
---

# Investigations

Design-space investigations feeding the [roadmap](../roadmap.md) register.

Each investigation dir holds a question/plan/findings/results chain; a partial chain means still-open work.

| Investigation | Question |
|---|---|
| [code-as-action-space/](code-as-action-space/README.md) | One `invoke(code)` tool as the model-facing action space — can the agent set up and manage tools, subagents, memory, and communication from Python, and does the evidence support it here? |
| [multi-agent-coordination/](multi-agent-coordination/README.md) | Complicated → complex: sibling agents that communicate and solve together |
| [watchdog/](watchdog/README.md) | A cheap, robust watchdog for the harness runtime |
| [benchmark-alternatives/](benchmark-alternatives/README.md) | Which external benchmark fits this codebase, and how the built-in suite extends |

## Contents

<!-- pb:index:start -->
<!-- GENERATED FILE — do not edit. Regenerate with pb-registers. -->
- [Benchmark Alternatives — Investigation](benchmark-alternatives/README.md) — Open investigation: which external benchmark (SWE-bench, Terminal-Bench, GAIA, BigCodeBench, aider Exercism, TheAgentCompany) fits this codebase, and how the built-in suite extends. Findings only; no decision yet.
- [Code-as-Action Space: the single `invoke(code)` tool](code-as-action-space/README.md) — Design space for a code-as-action agent surface: one `invoke(code)` tool that runs Python, so the agent sets up and manages tools, subagents, memory, and communication from code.
- [Communication Structures — Evidence Chain](communication-structures/README.md) — Auditable evidence chain (INVESTIGATION, PLAN, FINDINGS, RESULTS, raw metrics-cells.json) that compared four communication topologies on a fixed collaboration task.
- [Multi-Agent Coordination](multi-agent-coordination/README.md) — Design space for peer collaboration between sibling agents. Entry point is `INFO-148` (canonical record + open questions); conclusions are the canonical leaves.
- [Platform Evaluation: Porting the Harness Elsewhere](platform-evaluation/README.md) — Feasibility assessment for re-implementing Dynamic Harness' mechanically enforced guarantees as add-ons on top of an existing agent platform (OpenCode, Pi, DeepSeek Harness) instead of building tools and scaffolding from scratch, grounded in each platform's documented extension API as of 2026-09.
- [Plugin Investigation](plugin/README.md) — Interface-economy investigation feeding DL-8/DL-9 and AD-007: the runtime's plugin direction is a small set of host-agnostic seams with no loader / no late injection.
- [Watchdog — design space](watchdog/README.md) — Cheap, robust run-watchdog options for the harness runtime
<!-- pb:index:end -->
