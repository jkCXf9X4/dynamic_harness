---
id: INFO-007
type: info
title: "Host — DeepSeek Harness (dsh)"
summary: >
  DeepSeek Harness is the closest philosophical twin — native subagents, goals
  domain, spill store and token meter — but a dev preview with a nascent
  ecosystem, and loop safety remains yours to build.
date: 2026-09-23
status: current
---

# Host — DeepSeek Harness (dsh)

Repo: `deepseek-ai/deepseek-harness`.

- **Maturity:** **developer preview** — README: "THERE WILL BE
  COMPATIBILITY-BREAKING CHANGES".
- **Extension model:** Cordis plugin tree. "No privileged core": model
  adapter, tool registry, session log, and even the agent loop are plugins,
  replaceable from config (profiles + `cordis.patch.yml`).
- **Tool hooks:** highest-fidelity. Order: `tools/pre-execute` waterfall,
  then monotonic guards, then `tools/execute`, then `tools/post-execute`
  (accept/block/replace/add context), then frozen `tools/result` snapshot.
- **Native subagents:** yes — subagent subsystem with continuation service,
  fork/in-process drivers, ACP + codex + claude-code drivers.
- **Self-healing primitives:** goals domain (`active`/`paused`/`blocked`/
  `complete` + machine-routable block codes) — a ready home for blunt-vs-rot
  classification.
- **Result caching:** partially native — ships a **spill store**, a model-free
  **tool-result pruner**, and a **token meter**.
- **Loop-safety:** **not native** — repeated-call/near-identical detection is
  still yours to build as a plugin.
- **Ecosystem:** nascent — the "tested memory addons and RAG pipelines" that
  motivated this evaluation do not exist here yet.
- **Risk:** fast iteration with breaking changes. The plugin tree is powerful
  but young.
