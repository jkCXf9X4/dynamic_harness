---
title: "Verdict and Recommendation"
category: meta
summary: >
  Pi is the wrong substrate, DeepSeek Harness is the closest philosophical twin
  but fails the ecosystem motivation, and OpenCode is the pragmatic pick —
  commit the architecture, not the vendor.
parent: "README.md"
related:
  - fit-matrix.md
  - ../competitive-differentiation/README.md
---

# Verdict and Recommendation

## Verdict

1. **Pi is the wrong substrate for this harness.** The architectural moat —
   delegation, the deliverable gate, blunt-vs-rot with a shared budget —
   presumes a first-class parent/child task lifecycle. Pi explicitly ships
   without subagents or permission controls, so the hardest parts one wanted to
   shed return as process-spawned subagents with no in-process task graph. Its
   extension API is the friendliest, but the fit is the worst.
2. **DeepSeek Harness is the closest philosophical twin but fails the stated
   motivation.** Its tool pipeline has seams designed for exactly these
   guarantees; its goals state machine is a self-healing bootstrap; spill /
   token-meter / result-pruner pre-build much of the result-store and budget
   work. But it is a dev preview with a nascent ecosystem — the tested memory
   addons and RAG pipelines this evaluation sought are not there yet — and its
   loop safety (repeated-call detection) is *not* native and remains yours.
3. **OpenCode remains the pragmatic pick when the goal is the ecosystem.**
   Native subagents and persisted sessions buy delegation and checkpointing
   free; the tool-level guarantees must live in a Python MCP server (portable to
   any MCP host, including dsh and Claude), and loop-level guarantees in a thin
   TS plugin. Weakest of the three only on provenance (no first-class
   commit/artifact graph — adopt the host's session store).

## Recommendation

Commit the **architecture**, not the **vendor**:

- Keep the five mechanisms as a **language-neutral core** — they already are
  (`core/result_store.py`, the near-identical detectors, and spawn-limit
  signatures are pure Python).
- Ship **one Python MCP server**: result-caching + `result_read` + (optionally)
  guarded `bash`/`read`/`grep`/`glob`/`webfetch` wrappers. This is the ecosystem
  bridge — memory/RAG MCP addons plug in beside the guarantees.
- Ship **one thin TS plugin per host** for loop-level guarantees (loop
  detection, spawn caps) via that host's tool hooks.

Host tiebreak: **ecosystem today** → OpenCode; **philosophy + tolerance for
churn** → DeepSeek Harness (re-evaluate in 6–12 months when its third-party
plugin surface has formed). Pi only if terminal UX has been declared to outrank
the delegation model.

## Open follow-ups

- Prototype the `result-store` MCP server to prove the portability claim before
  committing a strategy.
- Stub a loop-safety plugin on the chosen host and run the benchmark suite
  (`dynamic_harness.benchmark`) against it; the mechanisms win only if they
  survive the port with the same measured behavior.
