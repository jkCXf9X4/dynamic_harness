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

The seed suggestion (from `__undeveloped_sugestions__.md`):

> Most policies react to some metric and inject or alter the prompt in some
> way — can you see if you can create a common interface for these to further
> facilitate the move towards a more plugin centric architecture.

`ReactivePolicyRegistry` (core/policies/interface.py) answered that for the
*metric-reactive* family — it is the reference for what a good seam looks like:
host-agnostic, narrow, stable. `docs/platform-evaluation.md` argues the core
worth porting is a ~25-tool tool-execution + spawn layer, reusing policies
without coupling.

**Purpose decision (Q1 answered):** this work is *porting and adaptation of the
current project structure into a more decoupled and manageable codebase* — the
internal-structure enabler. External porting (MCP server / third-party host
transport) belongs to `docs/platform-evaluation.md` and is **out of scope
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
on top — but that is `docs/platform-evaluation.md` territory, not this item.)

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
`docs/platform-evaluation.md`. This item only makes the codebase portable;
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
- **Q6 — Stdlib conversion:** open (see below).
- **Q7 — Deterministic testing:** open (see below).

## Open questions to resolve next

1. **ToolContext: facet or document?** Split the wide façade into role-scoped
   facets (e.g. environment/context-observation vs authority actions vs
   lifecycle), or keep one deliberately-broad contract and document it? The
   minimal-interface direction favors splitting; the cost is a registry that
   must hand over the right facet per tool. Which is the better first step?

   
2. **Policy application path (Q-unresolved).** Centralize every policy
   decision in the registry/runtime (one delegated path), or accept tool- and
   agent-embedded application? The near-identical/reactive work centralized;
   the tool-level policies (sandbox, bash-safety, webfetch, permissions,
   disclosure) still live inside individual tools.
3. **Stdlib conversion (Q6).** Is converting built-in tools/agents/policies
   into "registered defaults" a prerequisite (dogfooding) or a later cleanup?
   Cobblestone candidates: policies already have a registry; tools already
   have `register_default_tools`.
4. **Deterministic tests (Q7).** Where is the seam between "component list is
   injected by the test" and "registry defaults apply", so mock-LLM tests never
   depend on ambient state? (A `Runtime(..., plugins=[...])` explicitness
   boundary — without late loading.)
5. **The count.** A concrete inventory of "how many common interfaces exist"
   is step 1 below; its trimmed successor ("how few should exist") is the
   measurable success criterion. What number/names are acceptable?

## Investigation next steps

- [x] Decide the goal: interface economy (decouple + isolate + minimize
      interfaces); loader/late-injection explicitly out of scope
- [x] Record decisions Q1–Q5 (purpose / minimal manifest / crash loudly /
      default safety / code-only config)
- [ ] Enumerate every registration call site (`register_default_tools`,
      `register_agent_class`, `register_reactive_policy`, `on_*` handlers,
      `set_llm`, CLI wiring) into one canonical "what the host accepts" map
- [ ] List every common interface + its consumers + its breadth (start from
      `ToolContext`, the policy set, event handlers, `LLMProvider`,
      data types) → then propose the trimmed target set
- [ ] Audit the observed couplings: `ToolContext` façade surface, `compress`
      prompt inline in the façade, tool-level policy imports, direct actor
      reach from `ToolContext.status`/`kill`/`converse`
- [ ] Ruling: facet the ToolContext façade vs document-as-broad (open Q1)
- [ ] Ruling: registry-delegated vs tool-embedded policy application (open Q2)
- [ ] Design the explicit component-injection boundary for tests (open Q4)
- [ ] Pick the pilot seam (likely: policies — registry exists, reactive
      interface is the reference) and refactor it to be the demonstrated
      pattern for the rest
- [ ] Write the success criteria: fewer/narrower interfaces + no outside
      private-state reach + zero regressions on `pytest`; then decide stdlib
      conversion (open Q3)