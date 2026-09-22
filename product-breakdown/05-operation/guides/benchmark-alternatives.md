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
  - ../../01-product/use-cases/evaluation-and-qa.md
  - prompt-optimization.md
---

# Benchmark Alternatives — Comparison & Pros/Cons

This is the future-reference for *"how could we include a real/external bench,
and which one fits?"* It reviews the benchmark landscape against three
questions specific to this codebase:

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

---

## Decision summary

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
`ALL_TASKS` — keep them as opt-in `scripts/` pipelines (see the seam below).

---

## External benchmarks, individually

### SWE-bench (Full / Verified / Lite)

- **What:** the canonical agent benchmark. Each instance = `(repo, base_commit,
  problem_statement, gold_patch, FAIL_TO_PASS, PASS_TO_PASS)`. Given the repo at
  `base_commit` + the issue text, the agent produces a patch; the harness applies
  it to a clean checkout and runs `pytest -k "F2P or P2P"` — resolved iff all
  FAIL_TO_PASS pass and no PASS_TO_PASS regress. MIT, maintained by
  Princeton-NLP, 2.3k+ instances (500 in Verified).
- **Fits the harness structurally**: the F2P/P2P pytest gate *is*
  `verify(output_dir, scan_root)`, and a fresh `Runtime` + staged root is the
  "apply to a clean env" protocol the runner already does per run.
- **Why it's gold-standard**: real repos, real deps, real regressions — the
  strongest signal that an agent can actually change software.
- **Ease of use (gap)**:
  - Staging needs `git clone`, checkout at `base_commit`, and `pip install` of
    the downstream package (best done as per-instance Docker images; the current
    SWE-bench CLI is container-driven and expects ~120 GB disk / 16 GB RAM).
  - Deliverable is a **patch applied to the tree**, not a file in
    `.optimize_benchmarks/`; the verifier must reset + `git apply` + run pytest.
  - Runs are hours (pip installs + pytest per instance) — a batch pipeline, not
    the per-run feedback the prompt optimizer wants.
- **Recommendation**: keep as an **opt-in, batch** pipeline
  (`scripts/run_swebench.py`) behind a `BaseRepoTask.verify()` that delegates to
  `swebench` when installed. Add **one or two mini-SWE-bench fixture repos**
  (checked-in, deps-free, one failing test) to `ALL_TASKS` to get the
  repo-bugfix shape without Docker (this is the "SWE-bench-mini" plan).

### Terminal-Bench

- **What**: benchmark of terminal-computing tasks ("use the terminal to do X"),
  shipped as Docker images with a task dir (`/instruction`, `/workspace`, a
  `scripts/test.sh` and gold solution to verify). The agent interacts through a
  shell; success = the task's own `test.sh` passes against the achieved state.
  Used/initiated by terminal-focused agent tooling (e.g. Meta's CLI/agent
  efforts); MIT licensed, ~100+ tasks.
- **Fits this harness**: the `bash` tool is exactly the interaction the probe
  wants; verification is a file/dir state check, i.e. the same
  `verify(output_dir, scan_root)` contract.
- **Gaps**: each task is a container image (Docker required); some tasks do
  web/GUI things the harness's tools don't model; install + environment-heavy.
- **Verdict**: the closest external benchmark to this runtime's *operational*
  style (bash-first, artifact-on-disk), and worth building the mini version of:
  a checked-in corpus of ~5–10 single-fix tasks (`stub repo` + `test_issue.py`)
  evaluated by the identical `BenchmarkTask.verify()`.

### Aider's Exercism / polyglot benchmarks

- **What**: aider's classic code-editing loops — 133 Exercism Python practice
  exercises; take a stub module + instructions, implement it, pass the unit
  tests. Also the newer `polyglot` benchmark ("make the tests pass" across 200+
  files in many languages).
- **Where it's strong**: deps-free, stdlib-only, deterministic; the Exercism
  version needs no per-language env (only `python3`), so it's the **lowest-friction
  way to get a first external-bench signal**.
- **Where it's weak** for this repo: single-file edits, no repo to explore, and
  the harness already has `FibonacciTask` doing the same shape — adding it gives
  little *new* information; it won't stress delegation, context pruning, or
  multi-file workflows.
- **Verdict**: good as a cheap, quick smoke suite; not the headline benchmark.

### TheAgentCompany

- **What**: full-fidelity "software company" multi-agent benchmark — GitLab,
  Plane issue-tracker, ownCloud, RocketChat backends pre-seeded; 175 tasks
  across software engineer, data scientist, PM, HR, finance, admin roles. Agents
  browse the web via a simulated web server, write code, run commands, chat with
  other agents (NPCs).
- **Why it could matter here**: it's fundamentally *multi-agent* — the
  delegation/actor model is the target architecture; the harness's `ask`,
  `converse`, concurrent children could be exercised.
- **Why it doesn't fit well now**:
  - needs 6 Docker services + 30 GB free space + network setup;
  - primary grading is LLM-based (an LLM judge reads the trajectory) — this
    clashes with the project's "every `BenchmarkTask` carries a *failable
    ground-truth verifier*" invariant (../../01-product/use-cases/evaluation-and-qa.md).
  - adds all that infra for signal we can get cheaper from mini-fixtures.
- **Verdict**: skip as a *harness* task; if multi-agent-company signal is ever
  wanted, run `the-agent-company` externally and translate its deterministic
  subtasks into `BenchmarkTask`s.

### GAIA (HuggingFace `gaia-benchmark`)

- **What**: open-ended assistant benchmarks — questions like "Convert this
  wedding invitation to a CSV uploadable to Google Calendar, including the link",
  which require mixing web retrieval, tool use, and computation on real-world
  files. Grading is by exact-match string/human.
- **Why relevant here**: it's the "multi-source synthesis" case — exactly what the
  harness's `synthesis` task is a 1-file micro-version of; the parent-delegate-
  children-fuse structure is basically what GAIA rewards. `webfetch` + `bash` are
  already in-toolbox.
- **Cons**: needs network + a re-judge adapter (their exact-match strings are
  awkward against free-form agent output); pulls real-world file data.
- **Verdict**: the theoretical "best case" for this runtime's delegation story,
  but the automated verification is weak without building a judge.
- **BigCodeBench**: ~1,140 independent function-generation tasks over 100+
  real packages. **Pro**: embarrassingly parallel — delegate per-function to
  parallel children. **Con**: per-package dependencies mean the exact same
  env/Docker problem as SWE-bench; and in this repo the `parallel`
  `ParallelSubtasksTask` probes the same property much cheaper. **Verdict**:
  useful as an external sanity reference; overkill for prompt optimization.

### Single-function code benches (HumanEval, MBPP)

- One-sentence generation, evaluate by running the one function. Trivially
  easy to integrate (just another `BenchmarkTask` that runs the unit tests), but:
  no repo to explore, no multi-file, no agents — they measure raw code-space
  ability, not agentic capability. The existing `FibonacciTask` covers this
  noise. **Verdict**: skip.

---

## The built-in benchmark — what it already probes

The default `ALL_TASKS` suite (`src/dynamic_harness/benchmark/tasks.py` —
deterministic, failable, in-config, no Docker):

| id | What it checks | Probe |
|---|---|---|
| `discovery` | 3 largest `.py` files | file tooling |
| `codegen` | Fibonacci + assertions, run via `python3` | code-gen + verification |
| `analysis` | TODO/FIXME scan correctness | search + reporting |
| `manyfiles` | byte-sizes of `resources/_payload/*` one-at-a-time | long multi-step context, `prune`/`restore` |
| `parallel` | 8 sum-of-squares one per `resources/_parallel/*/input.txt` | **delegation**: children in parallel |
| `synthesis` | one `synthesis.txt` covering every token in `resources/_sources/*` | **delegation + fusion**: parent decompose, children gather, parent fuses |

The last two rows are deliberately **failable-but-not-forcing**: correctness
does not require delegation; the metrics (`agent_count`, `max_depth`, `turns`,
`cost`) reward prompts that actually use the parallel shape — the same signal
that would justify GAIA/BigCodeBench, at near-zero infra cost.

### Extension lanes that preserve the "no infra" property

1. **Fix-it task(s)** — a mini-SWE-bench fixture: a tiny repo (deps-free),
   file with a bug, a failing test, `verify` = `pytest` on the *applied*
   patch in a clean checkout. Adds the repo-level fix signal without Docker.
2. **Delegation-fact vs delegation-smooth** tasks — a *hard-to-delegate*
   baseline task where the "correct" strategy is inline (monolithic build –
   one root agent does it), to make the optimizer's delegation reward
   discriminating.
3. **Real-bench bridges** — keep SWE-bench (`verified`) meshwork, Terminal-Bench
   images, and GAIA as `scripts/`-adapter wrappers around a shared
   `apply_patch_then_pytest`/`dump_trajectory_to_file` primitive, running only
   in periodic batch, never in the per-prompt loop.

---

## Principles to preserve when adding any benchmark

1. The task's `verify()` must be **failable and ground-truth** — "pass by
   assertion, not by prose" (per-benchmark patch + `pytest` is good; LLM-judged
   grading is not).
2. Fresh `Runtime` per run, shared staged workspace and same `ALL_TASKS`
   consumes → reproducibility and baseline comparability.
3. Keep heavy/un-versioned things *outside* the default suite (the default
   suite is a per-feedback regressor for prompt optimization).
4. **Don't add a workload that can't be decomposed for delegation** and expect
   metrics to show a delegation benefit — no single-fix bench ever will.