---
id: INFO-070
type: info
title: "Plan — Comparison Bed"
category: investigation / plan
parent: "README.md"
summary: Reuses the existing benchmark infrastructure; the cell is the parameter
date: 2026-09-23
status: current
---

# The comparison bed

Reuses the existing benchmark infrastructure; the **cell is the parameter**:

| Piece | Reuse | New (implemented) |
|-------|-------|-----|
| Runner | `run_one(runtime_factory=..., task=..., ...)` (`benchmark/runner.py:84`) | `benchmark/comms.py` `run_cells`: per-cell `runtime_factory_for(cell)` + replicate loop |
| Metrics | `MetricsCollector` (`benchmark/metrics.py`) | Push-multiplier + contention counters + subscription sprawl can be added to `RunMetrics.extra` when needed (not yet wired) |
| Tasks | `BenchmarkTask` verifier pattern (`benchmark/tasks.py:60`) | `CollaborationTask(mode="independent"\|"interdependent")` + `resources/_collab` fixtures |
| Determinism | Tests' mock-agent pattern (`tests/conftest.py` `AgentTest`) | `_FixedLLM` stub in `test_comms_benchmark.py`: two replicates → identical metrics |
| Workspace | `stage_workspace` (`benchmark/runner.py:33`) | Minimal collab workspace helper in the test (`resources/_collab` + `.optimize_benchmarks`) |

Battery axes (canonical in `INFO-068`):
completion, quality (mechanical verifier), cost, context health (peak/final
footprint + push-multiplier), contention. Replicate count and variance budget
agreed before calling a loser on noise.