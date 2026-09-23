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

- [runtime-setup.md](runtime-setup.md) — minimal example, Runtime arguments, session reset.
- [delegation-patterns.md](delegation-patterns.md) — sequential, parallel, task-graph inspection.
- [events-and-usage.md](events-and-usage.md) — lifecycle handlers and token tracking.
- [artifacts-and-repository.md](artifacts-and-repository.md) — reading artifacts and commits.
- [custom-agent-classes.md](custom-agent-classes.md) — registering named agent types.
- [integration-example.md](integration-example.md) — complete end-to-end example.
- [error-handling.md](error-handling.md) — no-LLM mode and failure/escalation checks.
