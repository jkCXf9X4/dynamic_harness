---
id: INFO-120
type: info
title: Run the Built-in Scaler First
summary: Mock-LLM scaling benchmark — run it first to see which hot path grows superlinearly with turns or agents
date: 2026-09-23
status: current
---

# Run the Built-in Scaler First

```
python -m dynamic_harness.benchmark.profile_scaling            # full grid
python -m dynamic_harness.benchmark.profile_scaling --quick   # fast sanity pass
```

It uses a **mock LLM (no network)** and measures, in isolation, the scaling of
each suspected hot path. Read the *shading* column: a ratio that roughly doubles
when size doubles = **superlinear = suspect**. The tool prints four axes:

- **A** — Does `persist_checkpoint()` cost grow with conversation length? Axis: turns.
- **A2** — How many **bytes/tokens are actually SENT to the LLM** per turn? Axis: turns.
- **B** — Does `Repository.commit()` (full journal rewrite) grow with agent count? Axis: agents.
- **C** — Does the CLI snapshot (`StateWriter.snapshot`) grow with agent count? Axis: agents agg.
- **D** — End-to-end `Agent.run()` wall time at growing turn counts. Axis: end-to-end.

If the box this app runs in is CLI/REPL, C is usually the biggest "why did it get
so much slower than I expected". If it is the programmatic `Runtime` API, A2 and
A dominate over long conversations.

## Owns
- Scaler usage: commands, mock-LLM setup, how to read the shading column
- The five measured sections (A, A2, B, C, D) and their dominant axes

## Excludes
- Root-cause definitions and fix status: `INFO-119`
- Live-run diagnosis checklist: `INFO-116`
- Live profiler usage and artifacts: `INFO-117`
- Before/after measurement protocol: `INFO-118`
