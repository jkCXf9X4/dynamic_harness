# The Task Suite (One Front)

All tasks live in `src/dynamic_harness/benchmark/tasks.py` and are consumed by
every entry point:

| id | What it checks | Why it's included |
|---|---|---|
| `discovery` | 3 largest `.py` files by size | basic file tooling |
| `codegen` | Fibonacci + assertions, run via `python3` | code generation + verification |
| `analysis` | TODO/FIXME scan correctness | search + reporting |
| `manyfiles` | byte sizes of every file in `resources/_payload/`, processed one at a time | **long multi-step context**: ~16+ sequential tool calls, so it stresses and rewards `prune()`/`restore()` context management |
| `parallel` | 8 independent sum-of-squares sub-tasks, one per `resources/_parallel/*/input.txt` | **delegation probe**: an agent is told to delegate one child per subdirectory; metrics (`agent_count`, `max_depth`, `turns`) reveal whether the parallel parent-split shape is actually used |
| `synthesis` | one combined `synthesis.txt` covering every first-line token in `resources/_sources/*.txt` | **delegation/spawn probe**: children gather fragments, the parent fuses them into a single artifact — the "decompose → gather → fuse" shape |

The `manyfiles` task is the pruning probe — it builds a large transcript of
stale tool results, so a system prompt that guides agents to `prune()` finished
turns (and `restore()` when needed) scores lower prompt-token counts without
losing correctness. That is what makes the optimizer search for pruning-aware
prompts. The `parallel` and `synthesis` tasks probe the *other* axis: whether
the prompt steers the agent to delegate independent sub-problems instead of
serializing them in one context.
