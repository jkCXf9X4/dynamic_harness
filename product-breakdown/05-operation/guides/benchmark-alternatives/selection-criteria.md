# Selection Criteria & Decision Summary

Reviews the benchmark landscape against three questions specific to this
codebase:

1. **Ease of use** — how much Docker/env/network/pip machinery, and how well the
   harness's `BenchmarkTask.verify(output_dir, scan_root) -> (bool, note)`
   interface (see `src/dynamic_harness/benchmark/tasks.py`) maps onto it.
2. **Relevance** — does it exercise what this runtime is built for: a
   tool-calling agent (`bash`, `read/write/edit`, `webfetch`) with **actor-model
   delegation**, fresh-context sub-agents, artifact-driven communication, and a
   **failable ground-truth verifier**?
3. **Delegation payoff** — does the workload decompose into independent
   sub-tasks (where a parent can split, children run fresh-context, parent
   fuses)? Single-problem-fix benchmarks get *zero* benefit from delegation.

## Decision Summary

| Benchmark | Tests | Ease | Relevance | Delegation payoff | Verdict |
|---|---|---|---|---|---|
| **SWE-bench** (Full/Verified/Lite) | real GitHub issue → patch | Hard (Docker, ~120GB) | High | None | gold standard for repo fixes; infra-heavy batch eval only |
| **Terminal-Bench** | CLI/computing tasks, bash-facing | Medium (image per task) | High | Low | closest to the harness's bash-first style; mini version worth building |
| **Aider Exercism / polyglot** | single-file bug fix, stdlib-only | Trivial | Medium | None | no env needed, first cheap smoke suite — but least diagnostic |
| **TheAgentCompany** | simulated software company, multi-agent | Low (6 Docker services, 30GB) | Medium | Medium (cross-role coordination) | LLM-judged grading clashes with the "failable ground-truth verifier" rule |
| **GAIA** | open-ended assistant lookup + synthesis | Medium (network + judge adapter) | High | High | closest external analog to the in-tree `synthesis` probe |
| **BigCodeBench** | ~1140 independent function tasks | Hard (per-package deps) | Medium | High (embarrassingly parallel) | parallel-delegation stressor, but heavy envs |
| **HumanEval / MBPP** | single-function generation | Easy | Low | None | too narrow; has no repo/state to explore |

External benchmarks that **don't fit** should not be added to the default
`ALL_TASKS` — keep them as opt-in `scripts/` pipelines (see
[built-in-suite.md](built-in-suite.md)).
