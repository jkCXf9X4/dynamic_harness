---
id: INFO-200
type: info
title: Extension Points
summary: Agent classes, reactive policies, tools, and skills
date: 2026-10-10
status: current
---

# Extension Points

The seams a host uses to extend the runtime. Source: `src/dynamic_harness/core/`.

## Agent classes
- `Runtime.register_agent_class(name, cls)` registers a custom `Agent` subclass.
- `delegate(agent_type=...)` selects a registered class; unknown names are rejected, no silent fallback.
- `Runtime.registered_agent_classes()` lists the names.

## Reactive policies
- Contract in `core/policies/interface.py`: `Observation` (metric snapshot), `PromptInjection` (directive), `ReactivePolicy` (`name` + `evaluate(obs)`), `ReactivePolicyRegistry` (ordered runner).
- A policy decides; the host executes. No object in the module imports an agent or a runtime.
- `Runtime.register_reactive_policy(...)` adds a policy to the run loop.
- Built-in policies in `core/policies/`: agent, brief, budget, context, cost, disclosure, filesystem, heal, loop_guard, network, nudge, permissions, process, result_cache, retry, skill_inject, spawn, verify.

## Tools and skills
- `ToolRegistry.register(def, fn)` is public; a host adds tools the same way the defaults register.
- Skills: `agent.skills_dir` points at `<root>/<name>/SKILL.md` packages; triggers are injected into the system prompt, bodies load via `skill_load`.

## No plugin loader
- No plugin or loader module exists in `src/` (verified by grep).
- The plugin-readiness direction (seams first, no loader, no late injection) is an open investigation: `06-evolution/investigations/plugin/`.

## Owns
- The extension seams and their registration APIs.

## Excludes
- The plugin investigation's findings: `06-evolution/investigations/plugin/`.
- Policy design rationale: `02-architecture/`.
