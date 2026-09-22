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

- [runbook.md](runbook.md) — **NEW (fills GAP-5)**: tests, install/build, benchmark CLI, comms benchmark, pre-commit, release practice
- [guides/](guides/) — getting-started, programmatic-usage, custom-agents, extending-tools, prompt-optimization, benchmark-alternatives, performance-diagnostics