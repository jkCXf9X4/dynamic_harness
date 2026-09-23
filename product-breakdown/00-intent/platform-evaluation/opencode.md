---
title: "Host — OpenCode"
category: meta
summary: >
  OpenCode (anomalyco/opencode) is mature with native subagents and sessions;
  tool-level guarantees fit a Python MCP server and loop-level guarantees a thin
  TS plugin.
parent: "README.md"
related:
  - fit-matrix.md
---

# OpenCode (anomalyco/opencode + opencode.ai)

- **Maturity:** stable; mature plugin ecosystem, npm + local plugins.
- **Extension model:** TypeScript plugins (`.opencode/plugins/`,
  `~/.config/opencode/plugins/`, npm); load order defined, hooks run in sequence.
- **Tool hooks:** `tool.execute.before` / `tool.execute.after` — inspect args,
  block by throwing.
- **Native subagents:** yes — the `task` tool (subagent spawn) is the single
  choke point for spawn caps.
- **Session persistence:** native; checkpoint/resume across restarts is free.
- **Result caching:** not native — must be a tool-level adapter (e.g. a Python
  MCP server).
- **Ecosystem:** largest and best-tested (memory addons, RAG pipelines, MCP
  servers).
- **Language:** plugins are TS/Bun; the enforcement core is Python — needs a thin
  adapter split.
