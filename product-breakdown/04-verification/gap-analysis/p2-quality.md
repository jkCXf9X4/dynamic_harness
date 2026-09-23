---
title: "P2 Gaps — G9–G13"
category: meta
summary: >
  Quality-of-life / accuracy gaps: runtime cost reporting, message_count
  accumulation, doc/tool-count drift, agent-side provenance, and per-process heal
  budgets.
parent: "README.md"
---

# P2 — Quality-of-life / accuracy

## G9. Runtime reports tokens only; cost exists only in the benchmark

`config.llm.price_*` feed the benchmark (`benchmark/run.py:88-89`); the Runtime
`total_usage()` returns tokens (`usage.py:51-63`) and the CLI prints tokens. The
"cost" half of the cost/quality story is not available to a library consumer or
the CLI. **Status:** open.

## G10. `usage.message_count` is overwritten, not cumulative

`usage.py:36` set `message_count` to the latest send size rather than
accumulating, so `get_usage()["message_count"]` was the last message count, not
the total processed. Misleading for cost analysis. **Status:** RESOLVED —
`UsageTracker.record_usage` now accumulates (i.e. adds) `message_count`
(`usage.py`); `get_usage()["message_count"]` is the total messages processed.

## G11. Docs drift on tool count and extension surface

- `../../../docs/api/runtime.md:44` says "17 default tools"; `AGENTS.md` and
  `tools/registration.py` register **19**.
- `../../05-operation/guides/prompt-optimization.md:149-152` says the prompt loads
  "at agent.py:26"; it now loads in `core/prompts.py:13` (cosmetic).
- `LLMConfig.temperature`/`max_tokens` are never set from config — always
  defaults (`agent.py:335`, `config.py`).

**Status:** open.

## G12. No agent-facing provenance / trace tool

Failure triage (use-cases `../../01-product/use-cases/evaluation-and-qa.md`
Scenario C) requires reading `trace.jsonl` via `read`, and `/provenance`/`/trace`
are CLI-only commands. There is no `provenance`/`trace` tool, so a QA agent inside
a run can't self-audit its own branch. **Status:** open.

## G13. Heal budgets are per-process

`_heal_counts` is in-memory (`runtime.py:86, 350`); a `Runtime.resume` after a
process restart restarts heal budgets at zero, so bounded-retry guarantees do not
survive a restart (only the checkpoint/rot detection per run does). **Status:**
open.
