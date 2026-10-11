---
id: INFO-087
type: info
title: P2 Gaps — G9–G13
summary: Quality-of-life / accuracy gaps: cost reporting, message_count, doc/tool-count drift, provenance, heal budgets.
date: 2026-09-23
status: current
---

# P2 Gaps — G9–G13

## G9. Runtime reports tokens only; cost exists only in the benchmark

`config.llm.price_*` feed the benchmark (`benchmark/run.py:88-89`); the Runtime
`total_usage()` returns tokens (`usage.py:51-63`) and the CLI prints tokens. The
"cost" half of the cost/quality story is not available to a library consumer or
the CLI. **Status:** open — tracked by `IMP-011`.

## G10. `usage.message_count` is overwritten, not cumulative

`UsageTracker.record_usage` now accumulates `message_count` (`usage.py`);
`get_usage()["message_count"]` is the total messages processed. **Status:**
resolved.

## G11. Docs drift on tool count and extension surface

- `docs/api/runtime.md:44` says "17 default tools"; `AGENTS.md` and
  `tools/registration.py` register **34**.
- `05-operation/guides/prompt-optimization/` says the prompt loads "at
  agent.py:26"; it now loads in `core/prompts.py:13` (cosmetic).
- `LLMConfig.temperature`/`max_tokens` are never set from config — always
  defaults (`agent.py:335`, `config.py`).

**Status:** open — tracked by `IMP-012`.

## G12. No agent-facing provenance / trace tool

Failure triage (`INFO-023` Scenario C) requires reading `trace.jsonl` via
`read`, and `/provenance`/`/trace` are CLI-only commands. There is no
`provenance`/`trace` tool, so a QA agent inside a run cannot self-audit its own
branch. **Status:** open — tracked by `IMP-010`.

## G13. Heal budgets are per-process

`_heal_counts` is in-memory (`runtime.py:86, 350`); a `Runtime.resume` after a
process restart restarts heal budgets at zero, so bounded-retry guarantees do
not survive a restart (only the checkpoint/rot detection per run does).
**Status:** open — tracked by `IMP-009`.

## Owns
- G9–G13 gap states.

## Excludes
- The fixes: `IMP-011` (G9), `IMP-012` (G11), `IMP-010` (G12), `IMP-009` (G13).
