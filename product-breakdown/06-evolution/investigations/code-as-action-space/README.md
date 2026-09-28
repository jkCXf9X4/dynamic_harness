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