---
title: "Code-as-Action Space: the single `invoke(code)` tool"
summary: "Design space for a code-as-action agent surface: one `invoke(code)` tool that runs Python, so the agent sets up and manages tools, subagents, memory, and communication from code."
---

# Code-as-Action Space: the single `invoke(code)` tool

Design space for a **code-as-action** agent surface: one `invoke(code)` tool
that runs Python, so the agent sets up and manages tools, subagents, memory,
and agent communication from code (CodeAct lineage; sources in `INFO-142`).
Entry point is `INFO-141` (canonical record + open questions).

## Chain status

- **Question** — present, in `INFO-141`.
- **Plan** — present, in `INFO-146` and `INFO-143`.
- **Findings** — present, in `INFO-142`, `INFO-144`, `INFO-145`, `INFO-147`.
- **Results** — pending. No measurement yet; the decision gate is `INFO-146` §5.

## Leaves

| Area | Leaf |
|---|---|
| Canonical record + open questions | [INVESTIGATION.md](INVESTIGATION.md) |
| Benefit/cost evidence (CodeAct, Manus, Hermes, CodeMem, AgentFactory, and more) | [benefits-and-costs.md](benefits-and-costs.md) |
| Design proposal (hybrid: `invoke` + RPC stub + procedural skills) | [proposal.md](proposal.md) |
| Communication variants as probe surface (IMP-001..004) | [communication-experiments.md](communication-experiments.md) |
| Worker formation vs option load (frontier/modern asymmetry) | [worker-formation-option-load.md](worker-formation-option-load.md) |
| Self-improving context management (memory/summaries within the commit contract) | [context-management-improvement.md](context-management-improvement.md) |
| Build vs extend: development of the product or a new project (identity) | [build-vs-extend.md](build-vs-extend.md) |

## Contents

<!-- pb:index:start -->
<!-- GENERATED FILE — do not edit. Regenerate with pb-registers. -->
- **INFO-141** [Investigation — Code-as-Action: the single invoke(code) tool](INVESTIGATION.md) — Investigation of the code-as-action paradigm: one `invoke(code)` tool that runs Python, so the agent sets up and manages tools, subagents, memory, and communication from code. Question: where does this converge with or improve this harness.
- **INFO-142** [Benefits and costs — code-as-action evidence](benefits-and-costs.md) — Evidence for and against code-as-action, mapped to this harness: benefits (context/token economics, multi-tool success, self-evolution) and costs (security, injection, no determinism), with headline numbers cited inline.
- **INFO-143** [Build vs extend — is this a development of the product, or a new project?](build-vs-extend.md) — Is code-as-action a development of this product or a new project? Verdict: the hybrid capability is a development; the single-tool end-state is a new project on the shared skeleton.
- **INFO-144** [Communication experiments via code-as-action](communication-experiments.md) — Communication as the highest-leverage probe surface for code-as-action: four fixed topologies against open questions, with a variant matrix, three lab rules, and a concrete minimal experiment.
- **INFO-145** [Self-improving context management](context-management-improvement.md) — Should the agent improve its own context management (memory, summaries, compression)? Yes, in tiers: procedural skills yes, own context management bounded and measured, runtime machinery no.
- **INFO-146** [Proposal — hybrid code-as-action surface](proposal.md) — Hybrid code-as-action surface: keep the runtime rich, collapse only the model contract. An `invoke` tool plus a `harness_tools` RPC stub (policy parity) plus procedural-skill persistence, with guard changes and a measurement plan.
- **INFO-147** [Worker formation and option load](worker-formation-option-load.md) — Does cheap worker formation via `invoke(code)` confound the agent? The option-overload risk is inverted by model class: frontier agents rarely choke on options, weaker agents do and need a narrower surface.
<!-- pb:index:end -->
