---
title: "Investigation — Interface Economy: Decoupling Toward a Plugin-Ready Structure"
category: investigation
status: open
summary: >
  Direction work (before implementation) for making Dynamic Harness'
  internals decoupled and isolated: establish a minimal set of narrow, stable
  common interfaces between components (tools, policies, agent, runtime,
  artifact/memory, CLI). The structure should be plugin-ready — seams first,
  and replaceable components as a consequence — NOT a plugin architecture with
  late code injection.
---

# Direction: Plugin-Ready Structure Through Interface Economy

## The step being investigated

The harness is a monolith of *near-seams*: tools grouped by concern, policies
extracted into host-agnostic decision objects, a metric-reactive registry that
already calls itself "the plugin seam", an event bus, an LLM provider ABC. Each
surface is individually extensible in code — but the seams are *incidental*:
their shapes differ, their breadth varies, and components still reach across
them (observed couplings below).

This working item investigates a **structural goal, not a mechanism**:

> Establish and **minimize** the common interfaces between internal components,
> and **de-couple and isolate** those components behind them. A plugin
> architecture with late injection of code is **not** required — plugin-ready
> *structure* is the target; a loader is out of scope.

| Aspect | Today (extensible monolith) | Target (plugin-ready structure) |
|--------|------------------------------|---------------------------------|
| Common interfaces | Many, incidental, broad (`ToolContext`, policies, event fns, ABCs) | Few, explicit, **narrow** — each exposing only what its consumers need |
| Coupling | Components import each other directly across layers | Components know neighbors only through contracts |
| Isolation | Private state reachable through wide façades | No outside reach into internals; data types pure |
| Replaceability | By-hand subclass/register-over-name | A consequence of narrow seams, not a special feature |
| Late injection | None today (good) | **Stays out of scope** — no loader, no dynamic code loading |

The folder is named `plugin/` because the *vision* is plugin-centric structure;
this document deliberately argues against building plugin *infrastructure* now.

## Why this matters (motivating context)

The seed suggestion (from `../06-evolution/backlog.md`):

> Most policies react to some metric and inject or alter the prompt in some
> way — can you see if you can create a common interface for these to further
> facilitate the move towards a more plugin centric architecture.

`ReactivePolicyRegistry` (core/policies/interface.py) answered that for the
*metric-reactive* family — it is the reference for what a good seam looks like:
host-agnostic, narrow, stable. `../../00-intent/platform-evaluation.md` argues the core
worth porting is a ~25-tool tool-execution + spawn layer, reusing policies
without coupling.

**Purpose decision (Q1 answered):** this work is *porting and adaptation of the
current project structure into a more decoupled and manageable codebase* — the
internal-structure enabler. External porting (MCP server / third-party host
transport) belongs to `../../00-intent/platform-evaluation.md` and is **out of scope
here**.

## What already exists (interface inventory)

### The seams today

| Seam | Where | Shape | Breadth concern |
|------|-------|-------|-----------------|
| Metric-reactive policies | `ReactivePolicy` / `Observation` / `PromptInjection` / `ReactivePolicyRegistry` — `core/policies/interface.py:32-181`; registered per-factory via `Runtime.register_reactive_policy` (`core/runtime.py:464`) | Host-agnostic protocol + frozen dataclasses | **Reference model** — narrow, stable, host-agnostic |
| Tool façade | `ToolContext` (`core/tool_context.py`) handed to every tool fn in place of `Agent` | Concrete façade over `Agent` | **Wide** — see couplings below |
| Tool registry | `ToolDef` / `ToolResult` / `ToolRegistry.register(...)` + `openai_schemas()` (`core/tools/registry.py`); `register_default_tools` (`core/tools/registration.py:15`) | Registration call, schema builder | Registry is the load choke point; definitions split by concern |
| Decision policies | `AgentPolicy`, `SpawnPolicy`, `HealPolicy`, `RetryPolicy`, `LoopGuard`, `BashSafetyPolicy`, `SandboxPolicy`, … — `core/policies/` | Construct + pass in / subclass; no agent/runtime imports | Mostly pure; tools import some directly (see below) |
| Event handlers | `Runtime.on_report / on_escalation / on_failure / on_budget_request / on_activity` + `EventBus` (`core/events.py`) | Subscribe fn per event type | Fine; isolated dispatch already |
| LLM providers | `LLMProvider` ABC (`llm/provider.py`); `Runtime.set_llm` | ABC + injection | Textbook seam; clean |
| Agent classes | `Runtime.register_agent_class(name, cls)` (`core/runtime.py:454`) | Dict keyed by name | Bare; no descriptor/validation |
| CLI / state | `cli/terminal.py`, `cli/state.py` (`StateWriter`), `cli/present.py` | Code-level | Only consumer of agent-tree/state; fine as a shell |

### Observed couplings worth reviewing (the decoupling target)

- **`ToolContext` is a wide façade.** It exposes env, locks, llm, message
  buffer, usage, artifact/result stores, plan/checkpoint, compress/prune/
  restore, *and* authority actions (report/escalate/fail/kill/status/converse),
  plus direct reach into private state
  (`record_archived_artifact` appends to `agent._archived_artifact_ids`,
  `tool_context.py:104-109`). Every tool fn receives all of this; nothing
  restricts a file tool from pulling an agent's message buffer. Minimal
  interface = **facet the façade** (or accept one deliberately-broad façade
  and document it — decision needed).
- **`ToolContext.compress` builds its compression prompt inline**
  (`tool_context.py:126-136`) — policy-ish logic living in an interface
  object, not in a policy.
- **Tools import policies/task types directly.** `tools/agents.py` imports
  `policies.disclosure.DisclosurePolicy` and `policies.permissions.
  ToolPermissionPolicy`; `tools/context.py` imports `task.ActivityEvent`.
  Policies are host-agnostic, so this is not a layering violation per se —
  but it is an *un-centralized* decision path (policy applied inside a tool,
  not delegated by the registry). Worth an explicit ruling: is policy
  application registry-delegated (single path) or tool-embedded (many paths)?
- **`ToolContext.status`/`kill`/`continue_with_input` reach the agent actor
  directly** (`tool_context.py:199-228`) — coupling the tool façade to live
  agent lifecycle. Fine while ToolContext is the only door; a narrow-interface
  pass should list exactly which tools use which doorway methods.

## The target (working definition)

Not a plugin manifest/activation lifecycle. The target is **interface
economy** — a small, stable set of narrow contracts, with these properties:

1. **Few.** One contract per *kind* of exchange (observe-and-react, tool call,
   delegate, deliver report, persist state, generate) — not one per feature.
2. **Narrow.** Each interface exposes exactly what its consumers need; nothing
   private leaks through; no full-object handoffs where a view suffices.
3. **Stable.** The contracts hold across refactors; components change behind
   them, interfaces change rarely.
4. **Host-agnostic where possible.** Decisions (`core/policies/`) import
   neither agent nor runtime; data types (`Task`, `Artifact`, `Commit`,
   `Observation`, `PromptInjection`) are pure. Mirrors the reactive-policy
   reference model.
5. **Isolated.** Components know neighbors only through contracts; internals
   (agent context buffers, registry internals, store layouts) are private.
6. **Replaceable as a side effect.** Narrow seams + explicit
   register/inject points make swapping a tool, policy, handler, or provider a
   one-call act — without a loader, without monkey-patching.

## Design space / options to weigh

### A. Loader / late-injection plugin architecture — ❌ OUT OF SCOPE

No manifest schema, no directory scanning, no entry points, no activate/
deactivate lifecycle, no dynamic code loading. The user decided this is *not
needed*: the goal is structural, and a loader is machinery that buys nothing
until the seams are already minimal. Folded away so future work does not
re-litigate it. (If contracts do prove stable much later, a loader could sit
on top — but that is `../../00-intent/platform-evaluation.md` territory, not this item.)

### B. Seam-first refactor (the recommended path)

Do the interface work only, in the codebase's natural order: inventory →
narrow → isolate → consolidate registries. No new I/O, no new failure modes.

**Pros:** low risk; every change is a refactor with existing tests as the
guard (`pytest` mock-LLM determinism preserved); the reactive-policy refactor
already proved the pattern; produces the plugin-ready structure directly.
**Cons:** slower to see a "capability" land; requires discipline to avoid
churning interfaces for their own sake (explicit non-goal: reshuffling without
coupling reduction).

### C. Two-worlds (internal seams + external transport) — ❌ OUT OF SCOPE here

Serving the decision layer behind an MCP/third-party-host transport belongs to
`../../00-intent/platform-evaluation.md`. This item only makes the codebase portable;
it does not ship a transport. (Enablement: B enables C later.)

## Decisions (from review of the initial draft)

- **Q1 — Purpose:** porting/adaptation of the current project structure into a
  more decoupled and manageable codebase; external porting is out of scope.
- **Q2 — Manifest schema (if ever considered):** minimal (name/version/
  contributions); moot under "no loader".
- **Q3 — Failure/containment:** **crash loudly and warn in the terminal** —
  never silently swallow a broken component/registration.
- **Q4 — Safety boundary:** go with the default bias: policies replaceable,
  safety invariants frozen (loop detection, spawn limits, result handles,
  mutator set), tools additive, agent classes additive.
- **Q5 — Config interplay:** **start code-only**; components consume
  `harness.json` exactly as today, no merged per-component schema.
- **Q6 — Stdlib conversion:** NOT a prerequisite — defaults are registered
  through the same public register calls as anything else; no descriptor
  conversion. (Resolved ruling, §Resolved rulings ¶3.)
- **Q7 — Deterministic testing:** no discovery, ever — component lists are
  explicit or default, never scanned. (Resolved ruling, §Resolved rulings ¶4.)

## Resolved rulings (Q1–Q5 filled per direction)

1. **ToolContext: single contract, narrowed — NOT faceted.** Faceting would
   *multiply* the common-interface count, contradicting the primary goal
   ("minimize common interfaces"). Keep ONE `ToolContext` contract (count
   stays 1) and *narrow it*: move policy-ish logic out (the inline `compress`
   prompt → `ContextMetricPolicy`), replace direct private-state reaches
   (`record_archived_artifact` appending to `agent._archived_artifact_ids` →
   public `Agent` method), and document exactly what tools may touch. Tools
   state their needs in terms of the single public contract, never in terms of
   agent internals.
2. **Policy application path: registry-delegated for shared concerns,
   tool-embedded policy objects for domain guards.** No unified
   "policy-runner" mega-interface (that would be one more common interface).
   Shared every-tool concerns stay at the registry/runtime choke point
   (permissions, result-cache, truncation — already true). Tool-*specific*
   guards (sandbox, bash-safety, webfetch, disclosure) keep living in the tool,
   but always as host-agnostic policy objects invoked by it — never as inline
   logic or agent/runtime imports (already true; the inline `compress` prompt
   in the façade is the exception being fixed).
3. **Stdlib conversion: NOT a prerequisite.** There is no loader, so
   "defaults" means "registered through the public register calls the same way
   anything else would be" — already the case (`register_default_tools`,
   `register_agent_class`, `register_reactive_policy`). Built-ins are
   conceptually "the standard library"; no descriptor conversion adds value
   until the contracts are proven. Pilot seam = policies, demonstrated through
   the existing reactive registry.
4. **Deterministic tests: no discovery, ever.** Since no loader is built, there
   is *no* filesystem/ambient discovery boundary — none to design. Mock-LLM
   tests inject their components explicitly (construct policies / register
   tools on a fresh `Runtime`), exactly as they do today. This stays a hard
   rule: component lists are explicit or default; they are never scanned.
5. **The count — target common-interface set (~7):**

   | # | Interface | Where | Status |
   |---|-----------|-------|--------|
   | 1 | Tool call contract — `ToolDef` / `ToolResult` / `ToolContext` + `ToolRegistry` | `core/tools/` | Exists; narrowing in progress |
   | 2 | Metric-reactive policy — `Observation` / `PromptInjection` / `ReactivePolicy` / `ReactivePolicyRegistry` | `core/policies/interface.py` | Exists; the reference model |
   | 3 | Decision-policy objects (host-agnostic, import no agent/runtime) | `core/policies/` | Exists |
   | 4 | Event bus — `EventBus` + event payload types | `core/events.py`, `core/task.py` | Exists; isolated already |
   | 5 | LLM provider — `LLMProvider` ABC + response/call types | `llm/provider.py` | Exists; clean seam |
   | 6 | Agent-class registry — `register_agent_class` / `delegate(agent_type=)` | `core/runtime.py:454` | Exists; bare dict (fine for now) |
   | 7 | Persistent data types — `Task` / `ReportPayload` / `Artifact` / `Commit` / `AgentOutcome` (pure Pydantic) | `core/task.py`, `artifact/store.py`, `memory/repository.py` | Exists |

   Success = this set stays ≈7 and stable while couplings are removed, not
   interfaces added.

## Interface consumers + breadth audit

For each of the ~7 common interfaces: who consumes it, and how wide its
surface is. "Breadth" = members a consumer can see; the trimming rule is
*remove members no consumer uses* and *keep members used by ≥1 consumer*, even
if that consumer is a single tool.

### 1. Tool call contract (`ToolDef` / `ToolResult` / `ToolContext` + `ToolRegistry`)

`ToolContext` member → consumers (from `rg "ctx\."` across `core/tools/`):

| ToolContext member | Consumed by |
|--------------------|-------------|
| `artifact_store` | agents, artifacts |
| `generated_root` | filesystem, process, result_bash |
| `result_store` | registry, result_read, result_bash |
| `agent_id` | artifacts, context |
| `task_id` | agents, artifacts |
| `workspace_lock` | filesystem |
| `gitignore_filter` | filesystem |
| `repo_lock` | process |
| `llm` (→ `ctx.llm`) | context |
| `messages` | context |
| `usage_summary` | agents |
| `run_delegate_tool` | agents |
| `report` / `escalate` / `fail` | agents |
| `get_other_agent` | agents |
| `kill` / `resume_child` / `status` / `continue_with_input` | agents |
| `latest_assistant_message` | agents |
| `set_plan` / `checkpoint` | planning |
| `compress` / `prune` / `restore` | context |
| `emit_activity` | context |
| `record_archived_artifact` | artifacts |
| `message_count` | **NO tool** — dead surface (kept for tests/API symmetry); candidate for narrowing |

Observations:
- The `status`/`kill`/`resume_child`/`converse` cluster lives on the wide
  façade but **only the `agents` tool file consumes it** — a single consumer.
  Per the "keep members used ≥1" rule it stays; per narrowing it is the most
  self-contained slice (agent-authority actions), so if the façade is ever
  split by concern this cluster is the natural first facet.
- `message_count` is dead from the tools' perspective (the `usage` tool reads
  it through `usage_summary`, not directly) — remove or keep only for the
  public API symmetry.

### 2. Policy seams (decision objects + reactive)

Consumers of `core/policies/` by host component:

| Policy | Consumed by | Via |
|--------|-------------|-----|
| `AgentPolicy` | Runtime | `Runtime.__init__` → `from_config` |
| `SpawnPolicy` / `SpawnWarningPolicy` | Runtime / Agent | construction + delegate choke point |
| `HealPolicy` / `HealBudget` / `ResumePlanner` | Runtime / Agent | self-heal + resume |
| `LoopGuard` (+ helpers) | Agent | `_run_loop` |
| `RetryPolicy` / `TimeoutPolicy` / `TokenBudgetPolicy` | Agent | LLM call / loop |
| `NudgePolicy` | Agent | low-iteration / delegate nudges |
| `ToolPermissionPolicy` | Runtime, ToolRegistry, agents tool | role gating |
| `ResultCachePolicy` | ToolRegistry | snapshot/render |
| `DisclosurePolicy` | Runtime, agents, artifacts | progressive disclosure; `deliver_report` + tools |
| `BashSafetyPolicy` | process, result_bash | bash guard |
| `WebFetchPolicy` | network | fetch guard |
| `SandboxPolicy` | filesystem | path containment |
| `ContextMetricPolicy` | AgentContext, ToolContext | token estimate + compress prompt |
| `ReactivePolicy` / `Observation` / `PromptInjection` / `Registry` | Agent loop; Runtime factory registration | the reference seam |

The split matches the ruling: **shared concerns → registry/runtime choke point**
(permissions, result-cache, disclosure) and **domain concerns → tool-embedded
policy objects** (bash-safety, webfetch, sandbox). Nothing imports an agent or
runtime; the interfaces hold.

### 3. Event bus (`EventBus` + payload types)

Consumers: `Runtime.on_*` handling, `Harness` (`on_report`/`on_failure`/
`on_activity`), CLI (`events.jsonl` via StateWriter), telemetry/activity
emission from Agent. Handlers are isolated by `_dispatch`; `handler_counts()`
now exposes the seam for the canonical map. Breadth: 5 event kinds, each a
typed payload — no change needed.

### 4. LLM provider (`LLMProvider` ABC)

Consumers: Runtime (`set_llm`/injection), Agent (`generate_with_tools`,
retry/compress paths), `Harness._configure_llm`, benchmark/CLI wiring. One
ABC, one injection point — clean seam, no change.

### 5. Agent-class registry

Consumers: Runtime (`delegate` via `agent_type`), `tools/agents.py` delegate
tool. Bare dict today; the canonical map surfaces it. No change needed now.

### 6. Data types

Pure Pydantic models consumed across all layers (`Task`, `ReportPayload`,
`Artifact`, `Commit`, `AgentOutcome`, event payloads). No host logic inside —
the cleanest seam; no change.

### Trimmed target (what this audit proposes)

- **Keep the ~7 as-is.** The audit found no seam that should be added; the
  count holds.
- **Narrow `ToolContext` by dead surface:** `message_count` was the only
  member no consumer used — **removed** (after verifying no tool/test
  consumed it; `Agent.message_count` stays public).
- **Watch the single-consumer authority cluster.** If `agents.py` is ever
  split, `status`/`kill`/`resume_child`/`continue_with_input`/`get_other_agent`
  form the natural concern boundary — but no action today (one consumer keeps
  the "minimize interfaces" bias).
- **Leave tool-embedded domain policies untouched** — the ruling's steady
  state, and the audit confirms they add no cross-layer coupling.

## Investigation next steps

- [x] Decide the goal: interface economy (decouple + isolate + minimize
      interfaces); loader/late-injection explicitly out of scope
- [x] Record decisions Q1–Q5 (purpose / minimal manifest / crash loudly /
      default safety / code-only config)
- [x] Resolve the open questions into rulings (§Resolved rulings): ToolContext
      single+narrowed, policy application split (registry-delegated shared /
      tool-embedded domain), no stdlib descriptor conversion, no discovery in
      tests, ~7 common-interface target set
- [x] Enumerate every registration call site (`register_default_tools`,
      `register_agent_class`, `register_reactive_policy`, `on_*` handlers,
      `set_llm`, CLI wiring) into one canonical "what the host accepts" map —
      implemented as `Runtime.installed_components()` + `EventBus.handler_counts()`
      (single introspection surface, no registry-internal reach)
- [x] List every common interface + its consumers + its breadth — see
      §Interface consumers + breadth audit: ~7 contracts hold; `ToolContext`
      maps member-by-member; the single-consumer authority cluster is the only
      latent split point; `message_count` is dead surface
- [x] Audit the observed couplings: `ToolContext` façade surface, `compress`
      prompt inline in the façade, tool-level policy imports, direct actor
      reach from `ToolContext.status`/`kill`/`converse`
- [x] Ruling: keep ONE ToolContext, narrowed (facet rejected — multiplies
      interfaces)
- [x] Ruling: policy application = registry-delegated shared / tool-embedded
      domain policies, no mega-interface
- [x] Ruling: no discovery boundary needed — tests inject explicitly
- [x] **IMPLEMENTED** — pilot seam (policies + ToolContext narrowing):
      compress prompt moved into `ContextMetricPolicy.COMPRESS_PROMPT`,
      private `agent._archived_artifact_ids` reach replaced with public
      `Agent.record_archived_artifact`, `usage_summary` moved onto public
      `Agent.usage_summary` (no `_runtime`/`_iteration` reach), `pytest`
      green (466 passed)
- [x] **IMPLEMENTED** — dead surface trimmed: `ToolContext.message_count`
      removed (no tool/test consumer; `Agent.message_count` remains public),
      per the audit's trimming rule; `pytest` green (466 passed)
- [x] Write the success criteria: ~7 stable interfaces + no outside
      private-state reach + zero regressions on `pytest`; stdlib conversion
      stays off the table

## Success criteria (measurement)

1. **The count holds ≈7.** The common-interface set in §Resolved rulings ¶5
   does not grow while couplings are removed — refactors narrow or trade
   shapes, never add contracts.
2. **No outside private-state reach.** No module outside `Agent` touches
   `agent._*` (audit `rg "\._agent\b"` in `core/tools/` + `core/tool_context.py`
   → only public methods/properties). `Runtime._*` reach is confined to Runtime
   itself and its registered policies.
3. **One canonical map.** `Runtime.installed_components()` answers "what the
   host accepts" for tools, policies, agent classes, handlers, and the LLM —
   without any caller reaching into a registry's internals.
4. **Zero dead surface.** Every member of the ~7 interfaces is consumed by
   ≥1 caller, or it is removed (per the audit's trimming rule). `message_count`
   is the first removed instance; `Agent.message_count` stays public.
5. **Zero regressions.** Full `pytest` stays green (currently 466 passed). The
   two process-cancellation timing tests are known pre-existing flakes
   (`test_bash_cancel_kills_tree` / `test_bash_timeout_kills_grandchild`) — pass
   in isolation; unrelated to this work.
6. **No loader, ever.** No directory scanning, entry points, or late injection
   appears while pursuing the above; "plugin-ready" is delivered as structure,
   not machinery.