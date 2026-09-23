# Principles for Adding Any Benchmark

1. The task's `verify()` must be **failable and ground-truth** — "pass by
   assertion, not by prose" (per-benchmark patch + `pytest` is good; LLM-judged
   grading is not).
2. Fresh `Runtime` per run, shared staged workspace and same `ALL_TASKS`
   consumes → reproducibility and baseline comparability.
3. Keep heavy/un-versioned things *outside* the default suite (the default
   suite is a per-feedback regressor for prompt optimization).
4. **Don't add a workload that can't be decomposed for delegation** and expect
   metrics to show a delegation benefit — no single-fix bench ever will.
