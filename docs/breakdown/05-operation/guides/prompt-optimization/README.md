---
title: Prompt Optimization (Index)
summary: "Portable reference for the two-stage A/B-test workflow that optimizes the Dynamic Harness agent system prompt: how to run it, its inputs and outputs, and how to feed the winning prompt back"
---

# Prompt Optimization (Index)

Portable reference for the two-stage A/B-test workflow that optimizes the
Dynamic Harness agent system prompt: how to run it, its inputs and outputs, and
how to feed the winning prompt back into the application. See
[benchmark-alternatives](../../../06-evolution/investigations/benchmark-alternatives/README.md) for the external
benchmark landscape.

## Contents

<!-- pb:index:start -->
<!-- GENERATED FILE — do not edit. Regenerate with pb-registers. -->
- **INFO-128** [Customizing the Benchmark](customizing.md) — To add, remove, or change a task, edit and register it in `src/dynamic_harness/benchmark/tasks.py` (`ALL_TASKS`).
- **INFO-129** [Feeding the Optimized Prompt Back](feeding-back.md) — Three ways to apply the winning prompt: replace the seed file, per-agent override, or task-level override
- **INFO-130** [Files & Prerequisites](files-and-prerequisites.md) — The default `harness.json` uses DeepSeek flash and keeps the `provider_ignore` list to route around providers that cannot handle tool calling
- **INFO-131** [Outputs](outputs.md) — After a full run, `.optimize_benchmarks/` contains the variant prompts, per-run metrics, and the single best prompt
- **INFO-132** [Rate Limits & Provider Quirks](provider-quirks.md) — Free-tier models hit per-minute rate limits mid-run; use a paid/served model for full runs and `provider_ignore` for tool-refusing providers
- **INFO-133** [How to Run](running.md) — Clean the benchmark state, then run the optimization
- **INFO-134** [The Task Suite (One Front)](task-suite.md) — All tasks live in `src/dynamic_harness/benchmark/tasks.py` and are consumed by every entry point
- **INFO-135** [What This Does](workflow.md) — Given the baseline prompt (`src/dynamic_harness/core/agent_system_prompt.txt`), an orchestrator agent runs a two-round A/B test
<!-- pb:index:end -->
