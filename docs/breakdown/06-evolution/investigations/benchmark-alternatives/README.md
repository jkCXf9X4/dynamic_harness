---
title: "Benchmark Alternatives — Investigation"
summary: >
  Open investigation: which external benchmark (SWE-bench, Terminal-Bench, GAIA,
  BigCodeBench, aider Exercism, TheAgentCompany) fits this codebase, and how the
  built-in suite extends. Findings only; no decision yet.
---

# Benchmark Alternatives — Investigation

Question: which external benchmark fits this codebase, and how should the
built-in suite extend?

Status: **partial** — findings gathered, no decision. Still open.

Chain: question (this file) / findings (the survey leaves) / results (none
yet — no decision record).

Related: `INFO-023` (evaluation & QA use case), `INFO-090` (built-in suite).

## Contents

<!-- pb:index:start -->
<!-- GENERATED FILE — do not edit. Regenerate with pb-registers. -->
- **INFO-089** [Aider Exercism / Polyglot & Single-Function Benches](aider-and-small-benches.md) — Aider's Exercism Python practice exercises (133, stub + instructions, pass the unit tests) and the polyglot benchmark ("make the tests pass" across 200+ files); cheap smoke signal, not the headline benchmark.
- **INFO-090** [The Built-in Benchmark — What It Already Probes](built-in-suite.md) — The default ALL_TASKS suite (deterministic, failable, in-config, no Docker) and the extension lanes that keep the no-infra property.
- **INFO-091** [TheAgentCompany, GAIA & BigCodeBench](external-agent-benches.md) — TheAgentCompany (175 multi-agent company tasks, LLM-judged), GAIA (open-ended assistant synthesis), and BigCodeBench (~1,140 parallel function tasks) surveyed against the failable-verifier rule.
- **INFO-092** [Principles for Adding Any Benchmark](principles.md) — Four principles for adding any benchmark: failable ground-truth verify(), fresh Runtime per run, heavy work outside the default suite, and no workload that cannot decompose for delegation.
- **INFO-093** [Selection Criteria & Decision Summary](selection-criteria.md) — Reviews the benchmark landscape against three questions specific to this codebase
- **INFO-094** [SWE-bench (Full / Verified / Lite)](swe-bench.md) — SWE-bench (Full / Verified / Lite) — the canonical agent benchmark: instance = repo + base_commit + issue, patch verified by the F2P/P2P pytest gate; gold standard, infra-heavy, batch-only.
- **INFO-095** [Terminal-Bench](terminal-bench.md) — Terminal-Bench — terminal-computing tasks shipped as Docker images (task dir, test.sh, gold solution); the agent works through a shell, success = the task's own test.sh passes.
<!-- pb:index:end -->
