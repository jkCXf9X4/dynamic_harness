---
title: Operation Guides
summary: Workflow-specific guides complementing the runbook
---

# Operation Guides

Workflow-specific guides complementing the [runbook](../runbook/README.md).

| Guide | Use when |
|---|---|
| [Getting started](getting-started/README.md) | Installing, configuring, and running your first task |
| [Programmatic usage](programmatic-usage/README.md) | Embedding the runtime as a library (`Harness`/`Runtime`) |
| [Custom agents](custom-agents/README.md) | Subclassing and registering agent types |
| [Extending tools](extending-tools/README.md) | Registering custom tools |
| [Prompt optimization](prompt-optimization/README.md) | Running the metric-driven prompt benchmark |
| [Benchmark alternatives](benchmark-alternatives/README.md) | Choosing or comparing benchmark suites |
| [Performance diagnostics](performance-diagnostics/README.md) | Diagnosing scaling and cost |

## Contents

<!-- pb:index:start -->
<!-- GENERATED FILE — do not edit. Regenerate with pb-registers. -->
- [Benchmark Alternatives — Comparison & Fit](benchmark-alternatives/README.md) — Reference for choosing which benchmark(s) to run Dynamic Harness against. Reviews the main external agent/coding benchmarks (SWE-bench, Terminal-Bench, GAIA, BigCodeBench, aider Exercism, TheAgentCompany, web agents) plus the built-in suite's two extension axes (delegation probes, repo-bug-fix fixtures), each with ease-of-integration and relevance ratings against this runtime.
- [Custom Agents](custom-agents/README.md) — How to create custom Agent subclasses — overriding the run loop, adding hooks, injecting custom system prompts, and registering named agent types for programmatic delegation.
- [Extending Tools](extending-tools/README.md) — How to register custom tools in the ToolRegistry. Covers tool definition schemas, implementation signatures, accessing the calling agent, and integration patterns.
- [Getting Started](getting-started/README.md) — Quick start guide for Dynamic Harness. Covers installation, environment setup, running your first task, and understanding the output.
- [Performance Diagnostics (Index)](performance-diagnostics/README.md) — Methodology for finding why wall-clock time grows superlinearly with conversation length and agent count — most of it runtime/CLI bookkeeping, not LLM…
- [Programmatic Usage](programmatic-usage/README.md) — How to embed Dynamic Harness as a library. Covers constructing a Runtime, delegating tasks, handling events, token tracking, and integration patterns.
- [Prompt Optimization (Index)](prompt-optimization/README.md) — Portable reference for the two-stage A/B-test workflow that optimizes the Dynamic Harness agent system prompt: how to run it, its inputs and outputs…
<!-- pb:index:end -->
