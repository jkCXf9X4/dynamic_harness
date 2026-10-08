---
title: Layer 05 — Operation
summary: How do authors run, maintain, release?
---

# Layer 05 — Operation

**How do authors run, maintain, release?**

The operation layer makes the build/test/benchmark/release workflow explicit and executable — the convention's own verification loop ("run the repo's own build/test commands") depends on it. The runbook below is the canonical "how": `pytest` from the repo root, `pip install -e .` / `python -m build`, the benchmark CLI (metric-driven prompt benchmark), the comms benchmark (real-LLM topology comparison), pre-commit, and the release practice. Guides (getting-started, programmatic usage, custom agents, extending tools, prompt optimization, benchmark alternatives, performance diagnostics) are the complement for specific workflows.

## Owns
- Runbook, build/test/release workflow, release practice
- Benchmark/optimization run procedures
- Monitoring and diagnostics for how to maintain the runtime

## Excludes
- Design rationale, internals → `02-architecture/`
- Verification criteria, proof → `04-verification/`
- Backlog, roadmap → `06-evolution/`

## Contents

<!-- pb:index:start -->
<!-- GENERATED FILE — do not edit. Regenerate with pb-registers. -->
- [Operation Guides](guides/README.md) — Workflow-specific guides complementing the runbook
- [Runbook — dynamic_harness (Index)](runbook/README.md) — How authors install, test, benchmark, and release. All commands run from the repo root unless noted; Python 3.10+ required. Created 2026-09-21 (fills…
<!-- pb:index:end -->
