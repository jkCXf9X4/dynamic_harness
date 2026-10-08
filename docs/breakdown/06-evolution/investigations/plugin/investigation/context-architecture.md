---
id: INFO-182
type: info
title: "Plugin Direction — Context: How the References Build and Use It"
category: investigation
parent: "README.md"
summary: >
  Context is the real test of plugin-centricity: who contributes to the model's
  context, in what order, with what scope, and how it is observed. OpenCode V2
  and DeepSeek Harness both make context a contribution space, not a shared
  object; the harness's reactive-policy seam is the same shape — the gap is
  per-agent registration scoping.
date: 2026-09-28
status: current
pb_exempt: true
---

# Context: how OpenCode V2 and DeepSeek Harness build and work with it

Companion to `INFO-184`, focused on one axis:
**how each reference builds context and lets plugins work with it** — because
context is the shared, model-visible state of an agent runtime, so a
plugin-centric architecture is decided by who contributes to context, in what
order, with what scope, and how contributions are observed or vetoed.

## OpenCode V2 — per-request assembly, edited at boundary hooks

- **Build.** The system prompt is assembled from combined, non-overriding
  sources in a fixed order: agent/provider system prompt → built-in environment
  and date → Code Mode tool guidance → `AGENTS.md` files (discovered nearest-
  first from the workspace up, deduplicated, combined without conflict
  resolution) → skill/reference/MCP guidance → session instruction entries.
  Nested instruction files discovered during exploration are injected into
  session history in discovery order; edits to a loaded `AGENTS.md` are
  delivered as an "instruction update" before the next request.
- **Work with it.** Every model request is a rendered artifact that plugins
  edit at **ordered boundary hooks**, never inside: `session.hook("context")`
  hands a mutable draft of `event.system` / `event.tools` / `event.messages` /
  `event.options`, and later hooks see earlier edits. The changes affect only
  the outgoing call, not persisted history. `prompt` (admission) lets a plugin
  rewrite the user message before durable admission; `compaction` /
  `generate` / `title` are distinct request *kinds* so a plugin treats the loop
  and auxiliary calls differently. Reads are via `session.context({sessionID})`
  — the plugin context object `ctx` *is* a server client, not a shared
  in-process context.
- **Scoping.** Permissions are session-scoped rules that child sessions
  inherit; tool schemas are snapshotted per request; plugin instances are
  location-scoped (`ctx.location`).
- **Plugin-centricity enabled by:** the host owns assembly; plugins contribute
  by *registration order* at request boundaries, and the model request is
  immutable to later changes once captured.

## DeepSeek Harness — context as registered, scoped composition

- **Build.** The system-prompt package owns assembly out of **registered
  contributions**, each an effect-disposable registration in the plugin tree:
  `PromptSection` (ordered; static text or a per-assembly provider;
  `{{variable}}` interpolation; a `complete` section wins as the sole prompt),
  `PromptContext` (dynamic, cache-safe contributions rendered as durable
  user-role snapshots), tool-schema providers (`ToolProviderResult` with a
  pre-restriction `knownNames` universe), and prompt variables. Assembly
  gathers providers → detaches tool parameters → canonical order (ascending,
  then name) → runs the scope-filtered `system-prompt/assemble` waterfall
  (authoritative) → renders and commits the prompt as a `system/message`
  surface node in the session log.
- **Work with it.** The **session log is the source of context**:
  `deriveMessages()` projects model history from durable events; failed/
  retried attempts stay `assistant/attempt` and never enter model history
  ("model-visible means logged" is a runtime invariant). Plugins read through
  **projections** (`ctx.sessionProjections` folds committed events into typed
  state; plugin-owned message projections can rewrite what the model sees).
  Live interception: `agent.inject()` lands in the next admitted request;
  `agent/pre-step` (waterfall) rewrites or rejects claimed input; `agent/
  request` resolves the route.
- **Scoping.** `agent.ctx` is a **per-agent registration context** minted from
  the scope primitive: the same object governs both visibility and Cordis
  effect ownership. Scoped sections/contexts/tools **shadow globals by name**;
  `suppressRuntimeContext()` suppresses dynamic contributions in a scope;
  dispatch is scope-filtered; layers are reclaimed when empty.
- **Plugin-centricity enabled by:** context contributors are *registrations
  with the same effect semantics as every other plugin* — ordered, disposable,
  scoped, shadowable, suppressible, and subject to a `complete` veto. Two-sided
  surface: contribute (register) and intercept (waterfall events).

## The harness — per-agent code assembly, one narrow injection seam

- **Build.** Static system prompt (file, loaded at import) composed with
  role/brief steerage at construction (`build_system_prompt`, and the
  mission-command brief rendered *into the system steerage* because compress
  keeps only the system message). Per turn, a **code-rendered observation**
  (`build_observation`) restates turn count, token estimates, active turns,
  and the `FocusLedger` — deliberately not baked into the optimizable prompt
  text so reminders survive prompt optimization. Skill triggers sit in the
  stable system block (prompt cache); skill bodies load on demand.
- **Work with it.** `AgentContext` holds system/user/turns; the model drives
  prune/restore/compress itself. `PromptInjection` appends a tail user message
  (cache-prefix-safe) via the shared applier; `_inject_queue` wakes a blocked
  parent when a fire-and-forget child settles. Context persists to the
  checkpoint for resume; the trace `events.jsonl` mirrors live activity.
- **The context plugin surface is the metric-reactive seam**
  (`core/policies/interface.py`): `ReactivePolicyRegistry` evaluates ordered
  policies over an immutable `Observation`; each returns `PromptInjection`(s);
  the host applies them after all policies run (gather-then-apply, closer to
  dsh's assembly than OpenCode's in-place hook order). `add` replaces by name —
  a host overrides a default by re-registering, no loop change. Tools read
  context only through the narrow `ToolContext` façade; the EventBus stays
  notification-only.

## Comparison

| Axis | OpenCode V2 | DeepSeek Harness | Harness |
|---|---|---|---|
| Who owns the context object | host (server) | host (session log + assembly) | host (`AgentContext`) |
| Plugins contribute via | ordered boundary hooks | ordered, scoped registrations + waterfall | ordered policies → injections |
| Contribution order semantic | hook registration order | ascending order + name tiebreak; shadow by name | registration order; replace by name |
| Per-agent scoping | per-session (inherited) | `agent.ctx` — full scoped registrations | **runtime-level only** (no per-agent registration scope) |
| Read/observe | `session.context` API | projections + events | narrow `ToolContext`; EventBus (notify-only) |
| Injection | prompt hook (pre-admission) | `agent.inject` + `agent/pre-step` | `PromptInjection` tail append |
| Veto / replace whole prompt | edit `event.system` | `complete` section | construction-time role/prompt override only |
| Persistent context | native sessions | durable session log + projections | checkpoint + artifacts/trace |

## Lessons for the interface-economy direction

- **Validated — the static/dynamic split.** The references confirm the
  harness's discipline: stable steerage in a cache-friendly prefix (dsh
  `PromptSection`, OpenCode stable prefix) vs. dynamic per-request material
  (dsh `PromptContext` as user-role snapshots, OpenCode per-request edits,
  harness `build_observation` + tail injections). Keep `FocusLedger` and other
  reminders code-rendered, never baked into optimizable prompt text.
- **Adopt — scope the registration contract per agent.** dsh's `agent.ctx`
  scopes *every* contribution per agent; OpenCode scopes permissions per
  session. The harness scopes only comms subscriptions and skills roles
  (ad-hoc). Fold **per-agent scope keys into the one `Registration` contract**
  (design-comparison lesson 1): a policy/tool/context contributor can be bound
  to one agent. Lands inside the existing metric-reactive seam (#2) — no new
  interface, count stays ≈7.
- **Adopt (small) — make contribution semantics explicit on the seam.**
  Document that `ReactivePolicyRegistry` is ordered and that injections are
  gathered then applied by the host (not in-place), so policy authors know
  their directives never observe a sibling's injection. This is already the
  behavior; naming it is the work.
- **Non-adoption — no runtime `complete`/veto.** Full prompt replacement stays
  a construction-time concern (`build_system_prompt` role/override), never a
  runtime veto; a veto is too much authority for a single-tenant runtime and
  would add an interface.
- **Non-adoption — no per-request assembly waterfall.** The harness assembles
  context once per turn; a waterfall event on the EventBus would add an
  interface and duplicate the reactive-policy seam (consistent with
  design-comparison's non-adoptions).
- **Validated — durable context.** "Model-visible means logged" (dsh) and
  native checkpoints (OpenCode) both confirm the harness's artifact/commit/
  checkpoint + trace design; no new seam suggested.

## Verdict

Both references make context a **contribution space** (ordered, scoped,
disposable registrations / hooks) rather than a shared object plugins reach
into — which is exactly the harness's reactive-policy shape: the loop owns the
context, policies contribute through one narrow channel, the host applies. The
single material gap is **scope**: dsh and OpenCode bind contributions to an
agent/session, the harness binds to the runtime. That lands on the existing
seam as part of the registration-contract work (see
`INFO-189`).