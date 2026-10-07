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
