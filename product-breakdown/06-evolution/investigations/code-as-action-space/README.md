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

<!-- pb:index:start -->
- **INFO-141** [Investigation — Code-as-Action: the single invoke(code) tool](INVESTIGATION.md) — Design-space investigation into the code-as-action paradigm: giving the agent a single `invoke(code)` tool that executes Python so it can set up and manage tools, subagents, memory, and agent communication from code (CodeAct lineage: arXiv:2402.01030, Manus, Hermes, CodeMem, AgentFactory). Question: where does this converge with or improve this harness — which already has a `bash` do-anything tool, a lean-context ResultStore, a ToolContext that is RPC-shaped, and a skills layer that is procedural-memory-shaped. Recommendation: the model contract may collapse to (at most) one code tool, but the runtime keeps its rich, policy-enforcing surface behind an RPC stub — see proposal.md.
- **INFO-142** [Benefits and costs — code-as-action evidence](benefits-and-costs.md) — Sources are the works mapped in INVESTIGATION.md; the headline numbers are cited inline. The paradigm's core evidence is CodeAct (ICML 2024, arXiv:240…
- **INFO-143** [Build vs extend — is this a development of the product, or a new project?](build-vs-extend.md) — The code-as-action paradigm (single tool; the agent sets up and manages tools, worker groups, memory, and communication from Python) presents complex—…
- **INFO-144** [Communication experiments via code-as-action](communication-experiments.md) — Communication is the dimension where the design space is largest relative to what is built: four fixed topologies ( / / / ) against several still-open…
- **INFO-145** [Self-improving context management](context-management-improvement.md) — Should the agent be enabled to improve upon its own tools and context management — memory, summaries, compression, or similar — and how does that stay…
- **INFO-146** [Proposal — hybrid code-as-action surface](proposal.md) — RPC stub below) must route through so every code-driven action passes the same policies the tools enforce today — sandbox roots, spawn caps, plan/chec…
- **INFO-147** [Worker formation and option load](worker-formation-option-load.md) — lets any agent set up groups of collaborating workers — or standalone subagents — cheaply and structurally, addressing both complicated (breakdown/dec…
<!-- pb:index:end -->
