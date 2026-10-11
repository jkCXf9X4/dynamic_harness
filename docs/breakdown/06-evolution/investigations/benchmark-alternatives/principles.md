---
id: INFO-092
type: info
title: Principles for Adding Any Benchmark
summary: Four principles for adding any benchmark: failable ground-truth verify(), fresh Runtime per run, heavy work outside the default suite, and no workload that cannot decompose for delegation.
date: 2026-09-23
status: current
---

# Principles for Adding Any Benchmark

1. The task's `verify()` must be **failable and ground-truth** — "pass by
   assertion, not by prose" (per-benchmark patch + `pytest` is good; LLM-judged
   grading is not).
2. Fresh `Runtime` per run, shared staged workspace and same `ALL_TASKS`
   consumes to reproducibility and baseline comparability.
3. Keep heavy/un-versioned things *outside* the default suite (the default
   suite is a per-feedback regressor for prompt optimization).
4. **Don't add a workload that can't be decomposed for delegation** and expect
   metrics to show a delegation benefit — no single-fix bench ever will.

## Owns
- The four principles for adding any benchmark to the suite.

## Excludes
- The per-benchmark surveys — `INFO-089`, `INFO-091`, `INFO-094`, `INFO-095`.
- Selection criteria and the decision summary — `INFO-093`.
