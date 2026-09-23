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

- [what-is-solid.md](what-is-solid.md) — the capabilities that demonstrably back the use-cases
- [p0-mechanical-verification.md](p0-mechanical-verification.md) — G1 (open)
- [p0-delegate-heal.md](p0-delegate-heal.md) — G2 (resolved)
- [p0-progressive-disclosure.md](p0-progressive-disclosure.md) — G3 (resolved)
- [p0-artifact-linking.md](p0-artifact-linking.md) — G4 (resolved)
- [p1-sandbox-paths.md](p1-sandbox-paths.md) — G5 (resolved)
- [p1-custom-agent-types.md](p1-custom-agent-types.md) — G6 (resolved)
- [p1-layer2-heal.md](p1-layer2-heal.md) — G7 (partial)
- [p1-budget-plumbing.md](p1-budget-plumbing.md) — G8 (open)
- [p2-quality.md](p2-quality.md) — G9–G13

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
