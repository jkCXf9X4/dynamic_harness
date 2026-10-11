---
id: INFO-084
type: info
title: G6 — Custom agent classes cannot be spawned by the LLM
summary: P1 (resolved): the delegate tool accepts agent_type and validates it against registered classes.
date: 2026-09-23
status: current
---

# G6 — Custom agent classes cannot be spawned by the LLM

**Severity:** P1. **Status:** resolved.

**Current state:** `agent_type` is in the `delegate` tool schema and threaded
through `ToolContext.run_delegate_tool` to `Agent.run_delegate_tool`, which
validates against `Runtime.has_agent_class` and rejects unknown names (no
silent fallback to the base `Agent`). A parent in a live tree can choose a
registered specialist class for its child.

## Owns
- G6 gap outcome: the LLM can spawn custom agent classes.

## Excludes
- Custom-agent authoring: `05-operation/guides/custom-agents/`.
