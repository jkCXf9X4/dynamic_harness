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
| [Performance diagnostics](performance-diagnostics/README.md) | Diagnosing scaling and cost |

## Contents

<!-- pb:index:start -->
<!-- GENERATED FILE — do not edit. Regenerate with pb-registers. -->
- [Custom Agents](custom-agents/README.md) — How to create custom Agent subclasses — overriding the run loop, adding hooks, injecting custom system prompts, and registering named agent types for programmatic delegation.
- [Extending Tools](extending-tools/README.md) — How to register custom tools in the ToolRegistry: definition schemas, implementation signatures, accessing the calling agent, and integration patterns.
- [Getting Started](getting-started/README.md) — Quick start for Dynamic Harness: install, environment setup, first task, and output.
- [Performance Diagnostics (Index)](performance-diagnostics/README.md) — Methodology for finding why wall-clock time grows superlinearly with conversation length and agent count — most of it runtime/CLI bookkeeping, not LLM prompting
- [Programmatic Usage](programmatic-usage/README.md) — How to embed Dynamic Harness as a library. Covers constructing a Runtime, delegating tasks, handling events, token tracking, and integration patterns.
- [Prompt Optimization (Index)](prompt-optimization/README.md) — Portable reference for the two-stage A/B-test workflow that optimizes the Dynamic Harness agent system prompt: how to run it, its inputs and outputs, and how to feed the winning prompt back
<!-- pb:index:end -->
