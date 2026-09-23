---
title: "Host — DeepSeek Harness (dsh)"
category: meta
summary: >
  DeepSeek Harness is the closest philosophical twin — native subagents, goals
  domain, spill store and token meter — but a dev preview with a nascent
  ecosystem, and loop safety remains yours to build.
parent: "README.md"
related:
  - fit-matrix.md
---

# DeepSeek Harness (deepseek-ai/deepseek-harness, "dsh")

- **Maturity:** **developer preview** — README: "THERE WILL BE
  COMPATIBILITY-BREAKING CHANGES".
- **Extension model:** Cordis plugin tree; "no privileged core": model adapter,
  tool registry, session log, and even the agent loop are plugins, replaceable
  from config (profiles + `cordis.patch.yml`).
- **Tool hooks:** highest-fidelity: `tools/pre-execute` waterfall → monotonic
  guards → `tools/execute` → `tools/post-execute` (accept/block/replace/add
  context) → frozen `tools/result` snapshot.
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
- **Risk:** fast iteration with breaking changes; the plugin tree is powerful but
  young.
