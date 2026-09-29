---
title: Prompt Optimization (Index)
summary: "Portable reference for the two-stage A/B-test workflow that optimizes the Dynamic Harness agent system prompt: how to run it, its inputs and outputs…"
---

# Prompt Optimization (Index)

Portable reference for the two-stage A/B-test workflow that optimizes the
Dynamic Harness agent system prompt: how to run it, its inputs and outputs, and
how to feed the winning prompt back into the application. See
[benchmark-alternatives](../benchmark-alternatives/README.md) for the external
benchmark landscape.

## Contents

<!-- pb:index:start -->
- **INFO-128** [Customizing the Benchmark](customizing.md) — To add, remove, or change a task, edit and register it in . Each task is a subclass with a failable ground-truth that compares the agent's output arti…
- **INFO-129** [Feeding the Optimized Prompt Back](feeding-back.md) — The application loads its default system prompt at import time
- **INFO-130** [Files & Prerequisites](files-and-prerequisites.md) — uses DeepSeek flash and keeps the list to route around providers that cannot handle tool calling
- **INFO-131** [Outputs](outputs.md) — After a full run, contains
- **INFO-132** [Rate Limits & Provider Quirks](provider-quirks.md) — mid-run with . Use a paid/served model for full runs. calls. If the orchestrator returns empty output instead of tool calls, a guessed provider is ref…
- **INFO-133** [How to Run](running.md) — Clean the benchmark state, then run the optimization
- **INFO-134** [The Task Suite (One Front)](task-suite.md) — All tasks live in and are consumed by every entry point
- **INFO-135** [What This Does](workflow.md) — Given the baseline prompt , an orchestrator agent runs a two-round A/B test
<!-- pb:index:end -->
