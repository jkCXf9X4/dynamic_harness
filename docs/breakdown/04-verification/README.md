---
title: Layer 04 — Verification
summary: How do we know it satisfies requirements?
---

# Layer 04 — Verification

**How do we know it satisfies requirements?**

Verification is evidence-first, matching the repo's "verify before synthesize" ethos. This layer owns the **gap analysis** — an honest, severity-ranked audit (P0/P1/P2) of what the concepts and use-cases promise versus what the runtime and tools deliver, with per-gap evidence, the use-case it breaks, and status (G1–G13) — in `gap-analysis/`. The **communication-structures evidence chain** (INVESTIGATION, PLAN, FINDINGS, RESULTS, with raw `metrics-cells.json`) is the repo's model for verification-led design: a question, a design, measured evidence, a raw data chain. It lives under `06-evolution/investigations/communication-structures/` (`INFO-063` to `INFO-068`), not here.

## Owns
- Acceptance/test strategy and cases (see also `tests/`), numerical checks, reproducibility
- Gap analysis and its severity/status lifecycle

## Excludes
- New requirements → `01-product/`
- Architecture changes → `02-architecture/`
- Routine run commands → `05-operation/`
- Future work → `06-evolution/`
- Communication-structures evidence chain → `06-evolution/investigations/communication-structures/` (`INFO-063` to `INFO-068`)
- Decision records → the decision archive (`docs/archive/archive.zip`, `AD-*`)

## Contents

<!-- pb:index:start -->
<!-- GENERATED FILE — do not edit. Regenerate with pb-registers. -->
- [Gap Analysis — Concepts & Use-Cases vs Implementation](gap-analysis/README.md) — Honest audit of what the concepts (VISION, delegation model, artifact system, self-healing) and use-cases promise versus what the runtime and tools deliver: missing machinery, dead plumbing, and doc drift, each labeled P0/P1/P2 with evidence, the use-case it breaks, and status.
<!-- pb:index:end -->

## Tests

The executable test suite lives at the repo root: `tests/`. Run `pytest` from the repo root (see `05-operation/runbook/`). Open verification gaps from `gap-analysis/` are registered as IMPs in `06-evolution/roadmap.md`.
