---
title: "Programmatic Usage"
summary: How to embed Dynamic Harness as a library. Covers constructing a Runtime, delegating tasks, handling events, token tracking, and integration patterns.
---

# Programmatic Usage (Index)

Dynamic Harness can be embedded as a Python library — no CLI required — for
integrating agent workflows into applications, custom orchestrators, or
automated pipelines.

## Contents

<!-- pb:index:start -->
<!-- GENERATED FILE — do not edit. Regenerate with pb-registers. -->
- **INFO-121** [Artifacts & Repository](artifacts-and-repository.md) — Programmatic access to artifacts and the repository, covering artifact views, agent-written files, commit history, and the commit tree.
- **INFO-122** [Custom Agent Classes](custom-agent-classes.md) — How to subclass Agent, register a named agent class with the runtime, and delegate tasks to it by name.
- **INFO-123** [Delegation Patterns](delegation-patterns.md) — Patterns for delegating tasks programmatically: sequential chaining, parallel execution, and task graph inspection.
- **INFO-124** [No-LLM Mode & Error Handling](error-handling.md) — No-LLM mode behavior and how to inspect failed or escalated task results
- **INFO-125** [Events & Usage](events-and-usage.md) — Register callbacks for agent lifecycle events and track token usage per agent and across all agents
- **INFO-126** [Complete Integration Example](integration-example.md) — End-to-end Python example wiring an OpenAI provider, a Runtime, and a delegated Task into one async analysis run with report collection and usage reporting.
- **INFO-127** [Runtime Setup](runtime-setup.md) — Programmatic Runtime setup: minimal example, constructor arguments, and session reset
<!-- pb:index:end -->
