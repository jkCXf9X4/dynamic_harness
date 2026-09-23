# The Built-in Benchmark — What It Already Probes

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

## Extension Lanes That Preserve the "No Infra" Property

1. **Fix-it task(s)** — a mini-SWE-bench fixture: a tiny repo (deps-free), file
   with a bug, a failing test, `verify` = `pytest` on the *applied* patch in a
   clean checkout. Adds the repo-level fix signal without Docker.
2. **Delegation-fact vs delegation-smooth** tasks — a *hard-to-delegate*
   baseline task where the "correct" strategy is inline (monolithic build – one
   root agent does it), to make the optimizer's delegation reward
   discriminating.
3. **Real-bench bridges** — keep SWE-bench (`verified`) meshwork, Terminal-Bench
   images, and GAIA as `scripts/`-adapter wrappers around a shared
   `apply_patch_then_pytest`/`dump_trajectory_to_file` primitive, running only in
   periodic batch, never in the per-prompt loop.
