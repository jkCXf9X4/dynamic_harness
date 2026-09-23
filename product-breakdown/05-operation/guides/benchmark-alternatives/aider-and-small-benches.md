# Aider Exercism / Polyglot & Single-Function Benches

## Aider's Exercism / polyglot benchmarks

- **What**: aider's classic code-editing loops — 133 Exercism Python practice
  exercises; take a stub module + instructions, implement it, pass the unit
  tests. Also the newer `polyglot` benchmark ("make the tests pass" across 200+
  files in many languages).
- **Where it's strong**: deps-free, stdlib-only, deterministic; the Exercism
  version needs no per-language env (only `python3`), so it's the
  **lowest-friction way to get a first external-bench signal**.
- **Where it's weak** for this repo: single-file edits, no repo to explore, and
  the harness already has `FibonacciTask` doing the same shape — adding it gives
  little *new* information; it won't stress delegation, context pruning, or
  multi-file workflows.
- **Verdict**: good as a cheap, quick smoke suite; not the headline benchmark.

## Single-function code benches (HumanEval, MBPP)

- One-sentence generation, evaluate by running the one function. Trivially easy
  to integrate (just another `BenchmarkTask` that runs the unit tests), but no
  repo to explore, no multi-file, no agents — they measure raw code-space
  ability, not agentic capability. The existing `FibonacciTask` covers this
  noise. **Verdict**: skip.
