---
title: "Gap Analysis — Concepts & Use-Cases vs Implementation"
summary: >
  Honest audit of what the concepts (VISION, delegation model, artifact system,
  self-healing) and use-cases promise versus what the runtime and tools deliver:
  missing machinery, dead plumbing, and doc drift, each labeled P0/P1/P2 with
  evidence, the use-case it breaks, and status.
---

# Gap Analysis

An honest audit of the framework. "Missing" means one of: a **mechanism promised
by a concept but not implemented** (prompt discipline is not a mechanism), **code
that exists but is unreachable or inert**, or **documented behavior the code
contradicts**. Each gap cites evidence and the use-case it breaks, and is labeled
**P0** (breaks a core promise), **P1** (blocks a documented capability or a
real-world run), or **P2** (quality-of-life / accuracy).

## How to read a gap leaf

- **Current state** — the leaf states the outcome, present tense. A resolved gap states the fix in place; an open gap states what is still broken.
- **History** — dated narratives and before-states are not in the leaf; they are retired to the archive or compressed to the outcome line.
- **Tracking** — an open gap is tracked as an IMP in `06-evolution/roadmap.md`; the leaf points to the IMP by ID. The IMP's `status:` is the open/closed tracker.

## Contents

<!-- pb:index:start -->
<!-- GENERATED FILE — do not edit. Regenerate with pb-registers. -->
- **INFO-079** [G4 — artifact_ids are free-form; written files not linked](p0-artifact-linking.md) — P0 (resolved): written files now link to the artifact; read_artifact and provenance surface them.
- **INFO-080** [G2 — Delegation-boundary heal misses prose-completed children](p0-delegate-heal.md) — P0 (resolved): the delegate boundary heals on a missing deliverable, so a prose-completed child is recovered.
- **INFO-081** [G1 — VERIFY is prompt discipline, not a mechanism](p0-mechanical-verification.md) — P0 (open, IMP-005): the mandatory VERIFY step and plan acceptance criteria are never mechanically checked.
- **INFO-082** [G3 — Progressive disclosure is data, not an interface](p0-progressive-disclosure.md) — P0 (resolved): read_artifact takes a level parameter and raw_data is populated from written files.
- **INFO-083** [G8 — Budgeting / cost-control is dead plumbing](p1-budget-plumbing.md) — P1 (open, IMP-008): BudgetRequest plumbing exists but no tool exposes it and no spend cap is enforced.
- **INFO-084** [G6 — Custom agent classes cannot be spawned by the LLM](p1-custom-agent-types.md) — P1 (resolved): the delegate tool accepts agent_type and validates it against registered classes.
- **INFO-085** [G7 — Self-heal Layer 2 is not a distinct mechanism](p1-layer2-heal.md) — P1 (partial, IMP-012): the parent boundary reuses the root's shared _recover; the Layer 2 naming question remains.
- **INFO-086** [G5 — Sandbox rejects documented /tmp write patterns](p1-sandbox-paths.md) — P1 (resolved): examples use workspace-relative paths and artifact references; the sandbox error names the workspace root.
- **INFO-087** [P2 Gaps — G9–G13](p2-quality.md) — Quality-of-life / accuracy gaps: cost reporting, message_count, doc/tool-count drift, provenance, heal budgets.
- **INFO-088** [Gap Analysis — What Is Actually Solid](what-is-solid.md) — The capabilities that demonstrably back the use-cases, before the gaps.
<!-- pb:index:end -->

## Register

Each gap's severity and status live in its leaf (Contents above). Open gaps are
tracked as IMPs in `06-evolution/roadmap.md`:

- G1 `IMP-005`
- G7 `IMP-012` (partial)
- G8 `IMP-008`
- G9 `IMP-011`
- G11 `IMP-012`
- G12 `IMP-010`
- G13 `IMP-009`

Resolved (not re-registered): G2, G3, G4, G5, G6, G10.
