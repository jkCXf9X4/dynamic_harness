---
title: "Custom Agents"
category: guide
difficulty: advanced
summary: >
  How to create custom Agent subclasses — overriding the run loop, adding
  hooks, injecting custom system prompts, and registering named agent types
  for programmatic delegation.
related:
  - ../../../../docs/api/agent.md
  - ../../../../docs/api/runtime.md
  - ../programmatic-usage/README.md
---

# Custom Agents (Index)

Agent behavior can be customized by subclassing `Agent` and overriding key
methods. Custom agents are registered with the Runtime and referenced by name
during delegation.

## Contents

<!-- pb:index:start -->
- **INFO-096** [Basic Custom Agent](basic-agent.md) — `python from dynamic_harness.core.agent import Agent
- **INFO-097** [Agent with Custom State](custom-state.md) — `python from collections import Counter
- **INFO-098** [Full Example: Retry Agent](retry-agent.md) — An agent that automatically retries on failure up to N times
- **INFO-099** [Run Overrides](run-overrides.md) — Replace the entire execution loop
- **INFO-100** [System Prompt & Safety Limits](system-prompt-and-limits.md) — Pass a custom system prompt when constructing
- **INFO-101** [When to Use Custom Agents](when-to-use.md) — Logging/metrics — override with pre/post hooks
<!-- pb:index:end -->
