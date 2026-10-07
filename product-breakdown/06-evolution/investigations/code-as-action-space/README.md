---
title: "Code-as-Action Space: the single `invoke(code)` tool"
summary: "Design space for a code-as-action agent surface: give the agent one tool that runs Python, and let it set up and manage tools, subagents, memory, and…"
---

# Code-as-Action Space: the single `invoke(code)` tool

Design space for a **code-as-action** agent surface: give the agent one
`invoke(code)` tool that runs Python, and let it set up and manage tools,
subagents, memory, and agent communication from code (the CodeAct lineage — see
[benefits-and-costs.md](benefits-and-costs.md) for sources). Entry point is
[INVESTIGATION.md](INVESTIGATION.md) (canonical record + open questions); the
evidence analysis and the concrete design proposal are leaves.

| Area | Leaf |
|---|---|
| Canonical record + open questions | [INVESTIGATION.md](INVESTIGATION.md) |
| Benefit/cost evidence (CodeAct, Manus, Hermes, CodeMem, AgentFactory, …) | [benefits-and-costs.md](benefits-and-costs.md) |
| Design proposal (hybrid: `invoke` + RPC stub + procedural skills) | [proposal.md](proposal.md) |
| Communication variants as probe surface (IMP-001..004) | [communication-experiments.md](communication-experiments.md) |
| Worker formation vs option load (frontier/modern asymmetry) | [worker-formation-option-load.md](worker-formation-option-load.md) |
| Self-improving context management (memory/summaries within the commit contract) | [context-management-improvement.md](context-management-improvement.md) |
| Build vs extend: development of the product or a new project (identity) | [build-vs-extend.md](build-vs-extend.md) |

## Contents
