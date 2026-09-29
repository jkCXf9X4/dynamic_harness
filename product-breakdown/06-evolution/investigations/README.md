---
title: Investigations
summary: Design-space investigations feeding the roadmap register
---

# Investigations

Design-space investigations feeding the [roadmap](../roadmap.md) register.

| Investigation | Question |
|---|---|
| [code-as-action-space/](code-as-action-space/README.md) | One `invoke(code)` tool as the model-facing action space — can the agent set up and manage tools, subagents, memory, and communication from Python, and does the evidence support it here? |
| [multi-agent-coordination/](multi-agent-coordination/README.md) | Complicated → complex: sibling agents that communicate and solve together |
| [watchdog/](watchdog/README.md) | A cheap, robust watchdog for the harness runtime |

## Contents

<!-- pb:index:start -->
- [Code-as-Action Space: the single `invoke(code)` tool](code-as-action-space/README.md) — Design space for a code-as-action agent surface: give the agent one tool that runs Python, and let it set up and manage tools, subagents, memory, and…
- [Multi-Agent Coordination](multi-agent-coordination/README.md) — Design space for peer collaboration between sibling agents. The entry point is INVESTIGATION.md (canonical record + open questions); the conclusions a…
- [Plugin Investigation](plugin/README.md) — Interface-economy investigation feeding DL-8/DL-9 and AD-007: the runtime's plugin direction is a small set of host-agnostic seams with no loader / no…
- [Watchdog — design space](watchdog/README.md) — Cheap, robust run-watchdog options for the harness runtime
<!-- pb:index:end -->
