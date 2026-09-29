---
title: "Benchmark Alternatives — Comparison & Fit"
category: guide
summary: >
  Reference for choosing which benchmark(s) to run Dynamic Harness against.
  Reviews the main external agent/coding benchmarks (SWE-bench, Terminal-Bench,
  GAIA, BigCodeBench, aider Exercism, TheAgentCompany, web agents) plus the
  built-in suite's two extension axes (delegation probes, repo-bug-fix fixtures),
  each with ease-of-integration and relevance ratings against this runtime.
related:
  - ../../../01-product/use-cases/evaluation-and-qa.md
  - ../prompt-optimization/README.md
---

# Benchmark Alternatives (Index)

Future-reference for *"how could we include a real/external bench, and which one
fits?"* — the benchmark landscape reviewed against this codebase's needs.

## Contents

<!-- pb:index:start -->
- **INFO-089** [Aider Exercism / Polyglot & Single-Function Benches](aider-and-small-benches.md) — exercises; take a stub module + instructions, implement it, pass the unit tests. Also the newer benchmark ("make the tests pass" across 200+ files in…
- **INFO-090** [The Built-in Benchmark — What It Already Probes](built-in-suite.md) — The default suite ( — deterministic, failable, in-config, no Docker)
- **INFO-091** [TheAgentCompany, GAIA & BigCodeBench](external-agent-benches.md) — Plane issue-tracker, ownCloud, RocketChat backends pre-seeded; 175 tasks across software engineer, data scientist, PM, HR, finance, admin roles. Agent…
- **INFO-092** [Principles for Adding Any Benchmark](principles.md) — assertion, not by prose" (per-benchmark patch + is good; LLM-judged grading is not). consumes → reproducibility and baseline comparability. suite is a…
- **INFO-093** [Selection Criteria & Decision Summary](selection-criteria.md) — Reviews the benchmark landscape against three questions specific to this codebase
- **INFO-094** [SWE-bench (Full / Verified / Lite)](swe-bench.md) — problem_statement, gold_patch, FAIL_TO_PASS, PASS_TO_PASS) base_commit pytest -k "F2P or P2P" verify(output_dir, scan_root) Runtime .optimize_benchmar…
- **INFO-095** [Terminal-Bench](terminal-bench.md) — shipped as Docker images with a task dir (, a and gold solution to verify). The agent interacts through a shell; success = the task's own passes again…
<!-- pb:index:end -->
