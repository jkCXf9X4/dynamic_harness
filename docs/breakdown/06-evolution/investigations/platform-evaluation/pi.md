---
id: INFO-010
type: info
title: "Host — Pi"
summary: >
  Pi (earendil-works/pi-mono) has the friendliest extension API but no in-tree
  subagents or permission controls, so the delegation moat returns as
  process-spawned subagents with no in-process task graph.
date: 2026-09-23
status: current
---

# Host — Pi

Repo: `earendil-works/pi-mono` / `pi.dev`.

- **Maturity:** stable, popular terminal coding harness.
- **Extension model:** TypeScript extensions (`.pi/extensions/`,
  `~/.pi/agent/extensions/`), hot-reload with `/reload`. Runs TS via jiti, no
  compile step.
- **Tool hooks:**
  - `tool_call` — can **block** with `{block, reason, terminate}` and **mutate** args in place
  - `tool_result` — chainable middleware, can modify/truncate result
  - `context` — filter messages before each LLM call
  - `before_agent_start` — inject message / modify system prompt
- **Native subagents:** **none** — the README states Pi "skips features like sub
  agents and plan mode". Community extensions spawn sub-agents as processes.
- **Self-healing primitives:** native auto-retry + auto-compact + `agent_settled`
  (knows when the loop will not continue on its own).
- **Permission/sandbox:** **none built-in** — runs with full user permissions.
  Containerization is the documented answer.
- **Ecosystem:** growing (extensions, skills, themes, pi packages), but no
  in-tree memory/RAG addons.
- **Ceiling:** worst fit — the parent/child task graph that the delegation model
  and deliverable gate depend on is explicitly not shipped.
