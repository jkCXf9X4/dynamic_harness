---
title: "Custom Agents"
summary: How to create custom Agent subclasses — overriding the run loop, adding hooks, injecting custom system prompts, and registering named agent types for programmatic delegation.
---

# Custom Agents (Index)

Agent behavior can be customized by subclassing `Agent` and overriding key
methods. Custom agents are registered with the Runtime and referenced by name
during delegation.

## Contents

<!-- pb:index:start -->
<!-- GENERATED FILE — do not edit. Regenerate with pb-registers. -->
- **INFO-096** [Basic Custom Agent](basic-agent.md) — Subclass Agent, override run(), register the class, and delegate by name
- **INFO-097** [Agent with Custom State](custom-state.md) — Add per-agent state in __init__ and override _run_loop for custom behavior
- **INFO-098** [Full Example: Retry Agent](retry-agent.md) — An agent that automatically retries on failure up to N times
- **INFO-099** [Run Overrides](run-overrides.md) — Replace the entire execution loop
- **INFO-100** [System Prompt & Safety Limits](system-prompt-and-limits.md) — Pass a custom system prompt and safety limits when constructing an agent
- **INFO-101** [When to Use Custom Agents](when-to-use.md) — Match the need to the right override: hooks, preprocessing, prompt, limits, or retry
<!-- pb:index:end -->
