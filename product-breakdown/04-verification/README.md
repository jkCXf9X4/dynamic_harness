---
title: Layer 04 — Verification
summary: How do we know it satisfies requirements?
---

# Layer 04 — Verification

**How do we know it satisfies requirements?**

Verification is evidence-first, matching the repo's "verify before synthesize" ethos. Two threads live here: (1) the **gap analysis** — an honest, severity-ranked audit (P0/P1/P2) of what the concepts/use-cases promise vs what the runtime and tools actually deliver, with per-gap evidence, the use-case it breaks, a fix direction, and resolved/open status (G1–G13; G2–G6, G10 resolved); (2) the **communication-structures evidence chain** — the INVESTIGATION → PLAN → FINDINGS → RESULTS flow (with raw `metrics-cells.json`) that empirically compared four communication topologies on a fixed collaboration task. This is the repo's model for verification-led design: a question → design → measured evidence → raw data chain.

## Owns
- Acceptance/test strategy and cases (see also `tests/`), numerical checks, reproducibility
- Gap analysis and its severity/status lifecycle
- Benchmark evidence chains (communication-structures) and their raw data
- Verification decisions (ADRs with `VD` prefix)

## Excludes
- New requirements → `01-product/`
- Architecture changes → `02-architecture/`
- Routine run commands → `05-operation/`
- Future work → `06-evolution/`

## Contents

<!-- pb:index:start -->
- [Communication Structures — Evidence Chain](communication-structures/README.md) — The auditable INVESTIGATION → PLAN → FINDINGS → RESULTS flow (with raw ) that empirically compared four communication topologies on a fixed collaborat…
- [Gap Analysis — Concepts & Use-Cases vs Implementation](gap-analysis/README.md) — Honest audit of what the concepts (VISION, delegation model, artifact system, self-healing) and use-cases promise versus what the runtime and tools deliver: missing machinery, dead plumbing, and doc drift, each labeled P0/P1/P2 with evidence, the use-case it breaks, a fix direction, and status.
<!-- pb:index:end -->

## Tests

The executable test suite lives at the repo root: `tests/`. Run `pytest` from the repo root (see [05-operation runbook](../05-operation/runbook/README.md)). Open verification gaps from the [gap analysis](gap-analysis/README.md) are registered as IMPs in [06-evolution/roadmap.md](../06-evolution/roadmap.md).