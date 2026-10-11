---
id: INFO-009
type: info
title: "Host — OpenCode"
summary: >
  OpenCode (anomalyco/opencode) is mature with native subagents and sessions;
  tool-level guarantees fit a Python MCP server and loop-level guarantees a thin
  TS plugin.
date: 2026-09-23
status: current
---

# Host — OpenCode

Repo: `anomalyco/opencode` + `opencode.ai`.

- **Maturity:** stable. Mature plugin ecosystem, npm + local plugins.
- **Extension model:** TypeScript plugins (`.opencode/plugins/`,
  `~/.config/opencode/plugins/`, npm). Load order defined, hooks run in
  sequence.
- **Tool hooks:** `tool.execute.before` / `tool.execute.after` — inspect args,
  block by throwing.
- **Native subagents:** yes — the `task` tool (subagent spawn) is the single
  choke point for spawn caps.
- **Session persistence:** native. Checkpoint/resume across restarts is free.
- **Result caching:** not native — must be a tool-level adapter (e.g. a Python
  MCP server).
- **Ecosystem:** largest and best-tested (memory addons, RAG pipelines, MCP
  servers).
- **Language:** plugins are TS/Bun. The enforcement core is Python — needs a
  thin adapter split.
