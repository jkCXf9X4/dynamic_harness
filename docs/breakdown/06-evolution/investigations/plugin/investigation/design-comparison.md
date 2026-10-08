---
id: INFO-184
type: info
title: "Plugin Direction — Compared Designs: OpenCode V2 and DeepSeek Harness"
category: investigation
parent: "README.md"
summary: >
  The two reference plugin-centric architectures, mapped onto the ~7-interface
  target; what validates seam-first/no-loader, and the two lessons worth
  adopting (one registration contract, per-request tool snapshot).
date: 2026-09-28
status: current
pb_exempt: true
---

# Compared designs: OpenCode V2 and DeepSeek Harness

Every real plugin-centric platform ships a loader and a lifecycle. This leaf
asks whether the harness's "plugin-ready structure, no loader" direction still
holds when the two most instructive designs are on the table. Sources:
[OpenCode V2 plugin docs](https://opencode.ai/v2/docs/build/plugins/) and
[DeepSeek Harness architecture docs](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/architecture.md),
both fetched 2026-09-28.

## The two reference architectures

**OpenCode V2** — *domain transforms + runtime hooks around a fixed loop.*

- Every surface a plugin can touch is a **domain** (provider, model, agent,
  command, integration, MCP, reference, skill, tool, VCS, worktree, websearch).
  Each exposes read (`list`/`get`), write (`transform(editor)`), and
  `reload()`. Registrations are **ordered, replayable, reversible effects**:
  on reload every active transform replays in registration order onto a fresh
  value; `dispose()` drops one and rebuilds from the rest; reads are immutable
  snapshots.
- **Hooks** intercept live operations (prompt admission, per-request model
  context/compaction/generate/title, `http.request`/`response`, WS frames,
  retry decisions) — ordered, later hooks see earlier edits, drafts are
  mutable.
- **Tools** register via transform; each model request captures a **stable
  per-request snapshot**, so later transforms never mutate an in-flight
  request. Sessions, checkpoints, and permissions are native. The agent loop
  itself is **not** replaceable — plugins intercept around it.
- A loader exists (`Plugin.define` lifecycle, `.opencode/plugins/` + npm +
  config with options) but is thin: a package wrapper, not a composition
  language.

**DeepSeek Harness (dsh)** — *everything-is-a-plugin on Cordis.*

- **No privileged core**: the model adapter, tool registry, session log, and
  the agent loop itself are plugins, replaceable from config. Extension is by
  mounting a plugin beside the others; registrations unwind when it unloads.
- Composition is a layered tree: **profiles** stack **bundles** (config rows +
  code), patched by `cordis.patch.yml` layers + `--patch`, with HMR. `dsh
  --profile web --dump-config` prints the whole tree.
- **Events are the extension points**, in three domains: *session events*
  (durable facts appended to an append-only log — survive reload), *agent
  events* (`agent/*`, live in-flight interception), *capability events*
  (attach policy/adapters to seams). Waterfall events (`agent/pre-step`,
  `agent/request`, `llm/stream`, `tools/pre-execute`→`execute`→`post-execute`)
  must call `next()` — this is the loop-safety insertion point.
- **Seams** are Service Definition / Provider / Consumer triples; one provider
  swap moves a whole capability (a remote `fs` provider moves bash/PTY/LSP).
  Also ships a goals domain, spill store, token meter, per-agent scoped
  registrations (`agent.ctx`), and a projection seam.

## Mapping onto the ~7-interface target

| Harness interface | OpenCode V2 | DeepSeek Harness |
|---|---|---|
| 1 Tool call contract (`ToolDef`/`ToolResult`/`ToolContext`/`ToolRegistry`) | `ctx.tool` domain; namespaces; per-request snapshot | `ctx.tools` + `tools/pre\|post-execute` pipeline; registry is a plugin |
| 2 Metric-reactive policy (`Observation`/`PromptInjection`/`ReactivePolicy`) | closest: `session.hook("context")` (edit system/tools per call) | `agent/pre-step`, `agent/request`, `agent/*`; capability events |
| 3 Decision-policy objects (host-agnostic) | session-scoped permission rules; `retry` hook | sandbox/approval policy backend rows; capability seams |
| 4 Event bus (`EventBus` + payload types) | `ctx.event.subscribe` (public stream) | the three event domains — events **are** the extension surface |
| 5 LLM provider ABC | provider/model domains (transform to add/remove) | `ctx.llm` adapter seam (a plugin) |
| 6 Agent-class registry (`register_agent_class`) | `ctx.agent` domain; loop **not** replaceable | `ctx.agents` + `ctx.agentLoop` — both replaceable |
| 7 Persistent data types (`Task`/`Artifact`/`Commit`/…) | native sessions/checkpoints | session log + projections; persistence is a first-class seam |

The harness's seven contracts are the *contract half* of both architectures.
What the references add is the *machinery half*: uniform effect semantics
(dispose/replay/reload) and platform packaging (loaders, profiles, bundles,
plugin managers). Neither half is a new interface — both are a common shape
over the same seven seams.

## What this validates (no change to the direction)

- **Loader is platform machinery.** Both references spend real surface on
  packaging/activation/discovery/composition (dsh: profiles/bundles/patches +
  HMR; OpenCode: npm + `.opencode/plugins/` + config options). That buys
  nothing for a single-tenant runtime whose "composition order" is already the
  Python import order. Q2 (minimal manifest, moot), Q5 (code-only config),
  Q7 (no discovery) hold.
- **OpenCode V2's shape ≈ the Q4 ruling.** Its loop is fixed and plugins
  intercept around it — the same "safety invariants frozen, policies/tools
  replaceable" split. dsh's replaceable loop is the one place the harness's
  safety-by-construction stance and a plugin-centric core genuinely diverge.
- **Persistence/checkpoint is native in both** — matching the harness's
  artifact/commit/checkpoint types. No new interface suggested; the harness
  already owns the same guarantee at its own granularity.

## Lessons worth adopting (new work items)

1. **One registration contract.** Both references converged on a single
   disposition semantic — ordered add → a handle you can `dispose()`, with
   replay/rebuild semantics. The harness today has four heterogeneous register
   call sites (`register_default_tools`, `register_agent_class`,
   `register_reactive_policy`, `on_*`) unified only by introspection
   (`installed_components()`). Adopt one `Registration` contract (ordered add
   → `dispose()` handle + idempotent re-add) across the tool/policy/handler/
   agent-class registries. This *narrows* the existing seams — it does not add
   an interface, so the ≈7 count holds. No loader implied.
2. **Per-request tool snapshot.** OpenCode captures a stable executable tool
   snapshot per model request so later transforms can't desync an in-flight
   call. The harness re-renders `openai_schemas()` per turn; make the
   schema↔executor map immutable for the duration of a request (or forbid
   registry mutation mid-loop) so a mid-loop `unregister` cannot leave the
   model holding a tool the executor no longer has. Fits the existing
   mutator-set treatment of the tool contract.

## Explicit non-adoptions

- **No loader, profiles, bundles, or plugin manager** — reaffirm Q2/Q5/Q7; the
  platform-evaluation already routes the eventual transport there.
- **No dsh-style replaceable loop.** Q4 stands: loop detection, spawn limits,
  result handles, and the mutator set stay frozen in core. This is a
  deliberate divergence from dsh, not an oversight.
- **Do not evolve the EventBus into a waterfall/durable-event extension
  surface.** dsh's event domains are its seams; the harness already routes
  interception through narrow policies and state through artifacts/commits.
  Turning the notification-only bus into an ordered-intercept bus would add
  interfaces and duplicate existing seams — against the primary goal.

## Verdict

Seam-first, no-loader remains coherent and is *validated* by the comparison:
at the contract level OpenCode V2 and dsh are building the same interface
economy the harness is, and their extra machinery is only justified by
multi-tenant distribution. Adopt lesson 1 (registration contract) and lesson 2
(tool snapshot) as forward work; keep everything else as ruled. See
`INFO-189`.
