---
title: "Platform Evaluation: Porting the Harness Elsewhere"
category: meta
summary: >
  Feasibility assessment for re-implementing Dynamic Harness' mechanically
  enforced guarantees as add-ons on top of an existing agent platform
  (OpenCode, Pi, DeepSeek Harness) instead of continuing to build tools and
  scaffolding from scratch. Grounded in each platform's documented extension
  API and shipped subsystems as of 2026-09.
related:
  - competitive-differentiation.md
  - ../02-architecture/concepts/self-healing.md
  - ../02-architecture/concepts/delegation-model.md
  - ../04-verification/gap-analysis.md
---

# Platform Evaluation

This document evaluates whether Dynamic Harness' genuinely distinct claims can
be carried onto a third-party agent host as **add-ons**, returning the
commodity scaffolding (tool wiring, session persistence, memory addons, RAG
pipelines) to the host's ecosystem.

Framing follows `competitive-differentiation.md`: the claims worth porting are
only the **mechanically enforced** ones, because those are what survive model
disobedience:

1. Repeated-call / near-identical loop detection (fuzzy signatures)
2. Result caching behind opaque read-only handles (`result_read`)
3. Blunt-vs-rot self-healing with a shared heal budget + the deliverable gate
4. Spawn limits at a single choke point, with target signatures
5. Checkpoint persistence + cross-restart resumability

Everything else (progressive disclosure, provenance, fresh-context economics)
is either prompt-level, or provided by the host.

## The Portability Thesis

All five mechanisms live on a ~25-tool **tool-execution and spawn layer**, not
in the language runtime or model loop. That layer is exactly what a harness's
extension API exposes. A common shape recurs across the surveyed hosts:

- A **hook that can block or mutate a tool call before/after execution**
  (for loop detection, result caching, deliverable gating, token budgets)
- A **way to intercept agent spawning** (for spawn caps, parent/child model)
- **Persisted sessions** the host already maintains (for checkpoint replacement)

So the port is a thin adapter per host, wrapped around a language-neutral core
of the safety mechanisms.

## Host Summaries

### OpenCode (anomalyco/opencode + opencode.ai)

| Property | Finding |
|---|---|
| Maturity | Stable; mature plugin ecosystem, npm + local plugins |
| Extension model | TypeScript plugins (`.opencode/plugins/`, `~/.config/opencode/plugins/`, npm); load order defined, hooks run in sequence |
| Tool hooks | `tool.execute.before` / `tool.execute.after` — can inspect args, block by throwing |
| Native subagents | Yes — `task` tool (subagent spawn) is the single choke point for spawn caps |
| Session persistence | Native; checkpoint/resume across restarts is free |
| Result caching | Not native — must be a tool-level adapter (e.g. a Python MCP server) |
| Ecosystem | Largest and best-tested (memory addons, RAG pipelines, MCP servers) |
| Language | Plugins are TS/Bun; the enforcement core is Python — needs a thin adapter split |

### Pi (earendil-works/pi-mono / pi.dev)

| Property | Finding |
|---|---|
| Maturity | Stable, popular terminal coding harness |
| Extension model | TypeScript extensions (`.pi/extensions/`, `~/.pi/agent/extensions/`), hot-reload with `/reload`; runs TS via jiti, no compile step |
| Tool hooks | `tool_call` (can **block** with `{block, reason, terminate}` and **mutate** args in place), `tool_result` (chainable middleware — can modify/truncate result), `context` (filter messages before each LLM call), `before_agent_start` (inject message / modify system prompt) |
| Native subagents | **None** — the README states Pi "skips features like sub agents and plan mode"; community extensions spawn sub-agents as processes |
| Self-healing primitives | Native auto-retry + auto-compact + `agent_settled` (knows when the loop will not continue on its own) |
| Permission/sandbox | **None built-in** — runs with full user permissions; containerization is the documented answer |
| Ecosystem | Growing (extensions, skills, themes, pi packages), but no in-tree memory/RAG addons |
| Ceiling | Worst fit: the parent/child task graph that the delegation model and deliverable gate depend on is explicitly not shipped |

### DeepSeek Harness (deepseek-ai/deepseek-harness, "dsh")

| Property | Finding |
|---|---|
| Maturity | **Developer preview** — README: "THERE WILL BE COMPATIBILITY-BREAKING CHANGES" |
| Extension model | Cordis plugin tree; "no privileged core": model adapter, tool registry, session log, and even the agent loop are plugins, replaceable from config (profiles + `cordis.patch.yml`) |
| Tool hooks | Highest-fidelity: `tools/pre-execute` waterfall → monotonic guards → `tools/execute` → `tools/post-execute` (accept/block/replace/add context) → frozen `tools/result` snapshot |
| Native subagents | Yes — subagent subsystem with continuation service, fork/in-process drivers, ACP + codex + claude-code drivers |
| Self-healing primitives | Goals domain (`active`/`paused`/`blocked`/`complete` + machine-routable block codes) — a ready home for blunt-vs-rot classification |
| Result caching | Partially native: ships a **spill store**, a model-free **tool-result pruner**, and a **token meter** |
| Loop-safety | **Not native** — repeated-call/near-identical detection is still yours to build as a plugin |
| Ecosystem | Nascent — the "tested memory addons and RAG pipelines" that motivated this evaluation do not exist here yet |
| Risk | Fast iteration with breaking changes; the plugin tree is powerful but young |

## Fit Against the Five Mechanisms

| Mechanism | OpenCode | Pi | DeepSeek Harness |
|---|:---:|:---:|:---:|
| Loop detection (block/count per batch) | via `tool.execute.before` (throw) | via `tool_call` (block/terminate) | via guard + pre-execute waterfall |
| Result caching + `result_read` | via your MCP server (portable) | via `tool_result` middleware | **native** (spill + pruner) |
| Self-healing + deliverable gate | `session.error`/`session.idle` + native resume; deliverable gate is a hook | auto-retry/compact + `agent_settled`; but no task graph to gate against | **native goals domain** + subagent continuation |
| Spawn caps w/ target signatures | intercept `task` tool (~90% of the choke point) | **no in-tree subagents** → hard | **native** spawn signatures via subagent subsystem |
| Checkpoint/resume | **native** sessions | native sessions | **native** — persistence is a first-class seam |
| Permission/cost enforcement | native permissions; token budget is your hook | **none** — build or containerize | **native** approval + sandbox + token meter |

## Verdict

1. **Pi is the wrong substrate for this harness.** The architectural moat —
   delegation, the deliverable gate, blunt-vs-rot with a shared budget —
   presumes a first-class parent/child task lifecycle. Pi explicitly ships
   without subagents or permission controls, so the hardest parts one wanted
   to shed return as process-spawned subagents with no in-process task graph.
   Its extension API is the friendliest, but the fit is the worst.

2. **DeepSeek Harness is the closest philosophical twin but fails the stated
   motivation.** Its tool pipeline has seams designed for exactly these
   guarantees; its goals state machine is a self-healing bootstrap; spill /
   token-meter / result-pruner pre-build much of the result-store and budget
   work. But it is a dev preview with a nascent ecosystem — the tested memory
   addons and RAG pipelines this evaluation sought are not there yet. Its loop
   safety (repeated-call detection) is *not* native and remains yours.

3. **OpenCode remains the pragmatic pick when the goal is the ecosystem.**
   Native subagents and persisted sessions buy delegation and checkpointing
   free; the tool-level guarantees must live in a Python MCP server (which is
   portable to any MCP host, including dsh and Claude), and loop-level
   guarantees in a thin TS plugin. Weakest of the three only on provenance
   (no first-class commit/artifact graph — adopt the host's session store).

## Recommendation

Commit the **architecture**, not the **vendor**:

- Keep the five mechanisms as a **language-neutral core** (they already are
  — `core/result_store.py`, the near-identical detectors, and spawn-limit
  signatures are pure Python).
- Ship **one Python MCP server**: result-caching + `result_read` + (optionally)
  guarded `bash`/`read`/`grep`/`glob`/`webfetch` wrappers. This is the
  ecosystem bridge — memory/RAG MCP addons plug in beside the guarantees.
- Ship **one thin TS plugin per host** for loop-level guarantees (loop
  detection, spawn caps) via that host's tool hooks.

Host tiebreak: **ecosystem today** → OpenCode; **philosophy + tolerance for
churn** → DeepSeek Harness (re-evaluate in 6–12 months when its third-party
plugin surface has formed). Pi only if terminal UX has been declared to
outrank the delegation model.

Open follow-ups:

- Prototype the `result-store` MCP server to prove the portability claim
  before committing a strategy.
- Stub a loop-safety plugin on the chosen host and run the benchmark suite
  (`dynamic_harness.benchmark`) against it; the mechanisms win only if they
  survive the port with the same measured behavior.