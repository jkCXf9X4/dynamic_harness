---
title: "Host — Pi"
category: meta
summary: >
  Pi (earendil-works/pi-mono) has the friendliest extension API but no in-tree
  subagents or permission controls, so the delegation moat returns as
  process-spawned subagents with no in-process task graph.
parent: "README.md"
related:
  - fit-matrix.md
---

# Pi (earendil-works/pi-mono / pi.dev)

- **Maturity:** stable, popular terminal coding harness.
- **Extension model:** TypeScript extensions (`.pi/extensions/`,
  `~/.pi/agent/extensions/`), hot-reload with `/reload`; runs TS via jiti, no
  compile step.
- **Tool hooks:** `tool_call` (can **block** with `{block, reason, terminate}`
  and **mutate** args in place), `tool_result` (chainable middleware — can
  modify/truncate result), `context` (filter messages before each LLM call),
  `before_agent_start` (inject message / modify system prompt).
- **Native subagents:** **none** — the README states Pi "skips features like sub
  agents and plan mode"; community extensions spawn sub-agents as processes.
- **Self-healing primitives:** native auto-retry + auto-compact + `agent_settled`
  (knows when the loop will not continue on its own).
- **Permission/sandbox:** **none built-in** — runs with full user permissions;
  containerization is the documented answer.
- **Ecosystem:** growing (extensions, skills, themes, pi packages), but no
  in-tree memory/RAG addons.
- **Ceiling:** worst fit — the parent/child task graph that the delegation model
  and deliverable gate depend on is explicitly not shipped.
