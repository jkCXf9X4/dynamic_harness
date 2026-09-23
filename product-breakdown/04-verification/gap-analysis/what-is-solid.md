---
title: "Gap Analysis — What Is Actually Solid"
category: meta
summary: >
  The capabilities that demonstrably back the use-cases, before the gaps.
parent: "README.md"
---

# What Is Actually Solid

Before the gaps — the parts that demonstrably back the use-cases:

| Capability | Evidence | Serves use-cases |
|---|---|---|
| Parallel decomposition (batch delegates, gathered) | `agent.py:553-600, 709-742` | all families |
| Role-scoped tool allow-list enforced in code (orchestrator can't do hands-on work) | `tools/registry.py:27-44, 66-79` | repository-analysis, change |
| Prune/restore/compress context management | `context.py:126-275` + `manyfiles` benchmark | pipelines-and-jobs |
| Checkpoint persistence + `Runtime.resume` + CLI `/resume` | `checkpoint.py`, `runtime.py:190-243`, `terminal.py:436-443` | pipelines-and-jobs |
| Self-heal at the root boundary (resume-once / fresh worker) | `runtime.py:334-382` | all |
| Sandbox + SSRF guard + gitignore filter + path/repo locks | `tools/filesystem.py:96-105`, `network.py:30-59`, `runtime.py:99-140` | change, embedding |
| Token usage, JSONL traces, commits, `index.jsonl` provenance | `usage.py`, `trace.py`, `memory/repository.py`, `runtime.py:562-641` | evaluation-and-qa |
| Deterministic, failable benchmark verifiers + prompt optimizer | `benchmark/tasks.py`, `scripts/run_optimize.py` | evaluation-and-qa |
| 19 tools registered and extensible | `tools/registration.py` | embedding |
