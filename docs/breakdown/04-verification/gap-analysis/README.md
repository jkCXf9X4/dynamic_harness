---
title: "Gap Analysis — Concepts & Use-Cases vs Implementation"
category: meta
summary: >
  Honest audit of what the concepts (VISION, delegation model, artifact system,
  self-healing) and use-cases promise versus what the runtime and tools deliver:
  missing machinery, dead plumbing, and doc drift, each labeled P0/P1/P2 with
  evidence, the use-case it breaks, a fix direction, and status.
related:
  - ../../02-architecture/concepts/artifact-system.md
  - ../../02-architecture/concepts/self-healing.md
  - ../../02-architecture/concepts/delegation-model.md
  - ../../01-product/use-cases/README.md
  - ../../00-intent/VISION.md
---

# Gap Analysis

An honest audit of the framework. "Missing" means one of: a **mechanism promised
by a concept but not implemented** (prompt discipline is not a mechanism), **code
that exists but is unreachable or inert**, or **documented behavior the code
contradicts**. Each gap cites evidence and the use-case it breaks, and is labeled
**P0** (breaks a core promise), **P1** (blocks a documented capability or a
real-world run), or **P2** (quality-of-life / accuracy).

## Contents

<!-- pb:index:start -->
<!-- GENERATED FILE — do not edit. Regenerate with pb-registers. -->
- **INFO-079** [G4 — artifact_ids are free-form; written files not linked](p0-artifact-linking.md) — P0 (resolved): two disjoint stores meant a parent could not resolve a raw file path and the substantive file was never surfaced through read_artifact or provenance.
- **INFO-080** [G2 — Delegation-boundary heal misses prose-completed children](p0-delegate-heal.md) — P0 (resolved): the delegate boundary healed only on failure, so a child that completed in prose with no deliverable was never recovered.
- **INFO-081** [G1 — VERIFY is prompt discipline, not a mechanism](p0-mechanical-verification.md) — P0: the mandatory VERIFY step and plan acceptance criteria are never mechanically checked; blind synthesis is undetectable.
- **INFO-082** [G3 — Progressive disclosure is data, not an interface](p0-progressive-disclosure.md) — P0 (resolved): read_artifact returned every view at once and raw_data was dead, so the lazy-load economics were unachievable in the tool loop.
- **INFO-083** [G8 — Budgeting / cost-control is dead plumbing](p1-budget-plumbing.md) — P1 (open): BudgetRequest plumbing exists but no tool exposes it and no spend cap is enforced, so a run cannot be budgeted or stopped at a token ceiling.
- **INFO-084** [G6 — Custom agent classes cannot be spawned by the LLM](p1-custom-agent-types.md) — P1 (resolved): the delegate tool accepted no agent_type, so a parent in a live tree could not choose a registered specialist class.
- **INFO-085** [G7 — Self-heal Layer 2 is not a distinct mechanism](p1-layer2-heal.md) — P1 (partial): the parent boundary reuses the root's shared _recover, so the documented separate Layer 2 tier is a naming question, not a mechanism.
- **INFO-086** [G5 — Sandbox rejects documented /tmp write patterns](p1-sandbox-paths.md) — P1 (resolved): examples told agents to write to /tmp, which the sandbox always rejects, while the default CLI sandbox was the user's whole CWD.
- **INFO-087** [P2 Gaps — G9–G13](p2-quality.md) — Quality-of-life / accuracy gaps: runtime cost reporting, message_count accumulation, doc/tool-count drift, agent-side provenance, and per-process heal budgets.
- **INFO-088** [Gap Analysis — What Is Actually Solid](what-is-solid.md) — The capabilities that demonstrably back the use-cases, before the gaps.
<!-- pb:index:end -->

## Register

| # | Gap | Severity | Status |
|---|---|---|---|
| G1 | No mechanical verification; acceptance criteria unused | P0 | open |
| G2 | Delegate-boundary heal misses prose completions | P0 | resolved |
| G3 | Disclosure not progressive; `raw_data` dead | P0 | resolved |
| G4 | `artifact_ids` / files not linked to artifact | P0 | resolved |
| G5 | Sandbox vs `/tmp` examples; weak default isolation | P1 | resolved (docs + error msg) |
| G6 | LLM cannot spawn custom agent classes | P1 | resolved |
| G7 | Layer 2 heal is not distinct (see G2) | P1 | partial; naming question remains |
| G8 | Budget plumbing is inert | P1 | open |
| G9 | Runtime reports tokens only; cost only in benchmark | P2 | open |
| G10 | `usage.message_count` overwritten | P2 | resolved |
| G11 | Docs drift on tool count and extension surface | P2 | open |
| G12 | No agent-facing provenance / trace tool | P2 | open |
| G13 | Heal budgets are per-process | P2 | open |

Recommended next pass: **G8** (cost control) and **G1** (mechanical verification),
then **G13**/**G12** for resumability and agent-side self-audit. G11's tool-count
drift is a one-line docs fix.
