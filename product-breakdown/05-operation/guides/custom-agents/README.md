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

- [basic-agent.md](basic-agent.md) — minimal subclass, registration, delegation by name.
- [run-overrides.md](run-overrides.md) — replacing the loop and pre/post hooks.
- [system-prompt-and-limits.md](system-prompt-and-limits.md) — custom system prompts and safety limits.
- [custom-state.md](custom-state.md) — adding per-agent state.
- [retry-agent.md](retry-agent.md) — a retry-on-failure agent example.
- [when-to-use.md](when-to-use.md) — choosing an approach by use case.
