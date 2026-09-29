---
title: "Programmatic Usage"
category: guide
difficulty: intermediate
summary: >
  How to embed Dynamic Harness as a library. Covers constructing a Runtime,
  delegating tasks, handling events, token tracking, and integration patterns.
related:
  - ../../../../docs/api/runtime.md
  - ../../../../docs/api/agent.md
  - ../../../../docs/api/task.md
  - ../../../../docs/api/llm.md
---

# Programmatic Usage (Index)

Dynamic Harness can be embedded as a Python library — no CLI required — for
integrating agent workflows into applications, custom orchestrators, or
automated pipelines.

## Contents

<!-- pb:index:start -->
- **INFO-121** [Artifacts & Repository](artifacts-and-repository.md) — `python
- **INFO-122** [Custom Agent Classes](custom-agent-classes.md) — `python from dynamic_harness.core.agent import Agent
- **INFO-123** [Delegation Patterns](delegation-patterns.md) — `python
- **INFO-124** [No-LLM Mode & Error Handling](error-handling.md) — If you skip , agents enter no-LLM mode
- **INFO-125** [Events & Usage](events-and-usage.md) — Register callbacks for agent lifecycle events
- **INFO-126** [Complete Integration Example](integration-example.md) — `python import asyncio from pathlib import Path from dynamic_harness.core.runtime import Runtime from dynamic_harness.core.task import Task from dynam…
- **INFO-127** [Runtime Setup](runtime-setup.md) — `python import asyncio from pathlib import Path from dynamic_harness.core.runtime import Runtime from dynamic_harness.core.task import Task from dynam…
<!-- pb:index:end -->
