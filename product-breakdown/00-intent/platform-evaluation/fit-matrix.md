---
title: "Fit Against the Five Mechanisms"
category: meta
summary: >
  Each portability mechanism mapped onto OpenCode, Pi, and DeepSeek Harness:
  what is native, what needs a hook, and what is effectively absent.
parent: "README.md"
related:
  - portability-thesis.md
---

# Fit Against the Five Mechanisms

| Mechanism | OpenCode | Pi | DeepSeek Harness |
|---|---|---|---|
| Loop detection (block/count per batch) | via `tool.execute.before` (throw) | via `tool_call` (block/terminate) | via guard + pre-execute waterfall |
| Result caching + `result_read` | via your MCP server (portable) | via `tool_result` middleware | **native** (spill + pruner) |
| Self-healing + deliverable gate | `session.error`/`session.idle` + native resume; deliverable gate is a hook | auto-retry/compact + `agent_settled`; but no task graph to gate against | **native goals domain** + subagent continuation |
| Spawn caps w/ target signatures | intercept `task` tool (~90% of the choke point) | **no in-tree subagents** → hard | **native** spawn signatures via subagent subsystem |
| Checkpoint/resume | **native** sessions | native sessions | **native** — persistence is a first-class seam |
| Permission/cost enforcement | native permissions; token budget is your hook | **none** — build or containerize | **native** approval + sandbox + token meter |
