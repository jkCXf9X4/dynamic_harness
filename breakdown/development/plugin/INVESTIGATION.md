---
title: "Investigation — Toward a Plugin-Centric Architecture"
category: investigation
status: open
summary: >
  Direction work (before implementation) for making Dynamic Harness a
  plugin-centric runtime: a thin host core where tools, policies, agent
  classes, event handlers, LLM providers, and CLI surfaces are uniformly
  pluggable, discoverable, and replaceable — without touching the run loop.
---

# Direction: Toward a Plugin-Centric Architecture

## The step being investigated

Today the harness is a monolith of *near-seams*: tools grouped by concern,
policies extracted into host-agnostic decision objects, event-bus handlers, a
reactive-policy registry that already calls itself "the plugin seam". Each
surface is individually extensible in code, but there is no **uniform plugin
contract**, no **discovery/loading**, and no **lifecycle** — so "plugins" are
an idiom you implement by hand, not a capability you install.

This working item investigates the step from **extensible monolith** to
**plugin-centric host**:

| Aspect | Extensible today (default) | Plugin-centric (target) |
|--------|----------------------------|-------------------------|
| Extension mechanism | Register in code, per-surface | One plugin descriptor + one loader |
| Discovery | Read the source, import the right hook | Declarative: scan a dir / entry point, load, wire |
| Contract | Each seam has its own shape (`ReactivePolicy`, `ToolDef+fn`, agent class, event fn) | A shared `Plugin` interface that *contributions* into each seam |
| Lifecycle | Nothing: registrations live as long as the runtime | Install → activate → verify health → deactivate, at load or mid-run |
| Replace defaults | Subclass / monkey-patch / register-over-name | Explicit precedence + override semantics |
| Portability | Policies reusable, tools coupled to core types | Core is a thin host; everything else is a plugin (see `docs/platform-evaluation.md`) |

## Why this matters (motivating context)

The seed suggestion (from `__undeveloped_sugestions__.md`):

> Most policies react to some metric and inject or alter the prompt in some
> way — can you see if you can create a common interface for these to further
> facilitate the move towards a more plugin centric architecture.

`ReactivePolicyRegistry` (core/policies/interface.py) answered exactly that for
the *metric-reactive* family. `docs/platform-evaluation.md` argues the core
worth porting is a ~25-tool tool-execution + spawn layer, and that a plugin
host should reuse policies without coupling. This working item is the internal
mirror of that thesis: make the harness itself plugin-centric so both (a) the
codebase is clearly a host, and (b) third-party hosts / MCP extensions can be
served by the same seams.

## What already exists (implemented seams)

| Seam | Where | Extendable today? | Plugin shape needed? |
|------|-------|------------------|----------------------|
| Metric-reactive policies | `ReactivePolicy` / `Observation` / `PromptInjection` / `ReactivePolicyRegistry` — `core/policies/interface.py:32-181`; registered per-factory via `Runtime.register_reactive_policy` (`core/runtime.py:464`, "the plugin seam") | Yes — register, ordered, replace-by-name | Contract is good; needs discovery/loading |
| Tools | `ToolRegistry.register(ToolDef, fn)` + `openai_schemas()` (`core/tools/registry.py`); `register_default_tools(registry)` (`core/tools/registration.py:15`) | Yes — any async fn with `ToolContext` | ToolDef+fn is de-facto a plugin; needs a name/namespace + load path |
| Custom agent classes | `Runtime.register_agent_class(name, cls)` (`core/runtime.py:454`); used by `delegate` via `agent_type` | Yes | Bare dictionary; no descriptor/validation |
| Event handlers | `Runtime.on_report / on_escalation / on_failure / on_budget_request / on_activity` + `EventBus` (`core/events.py`) | Yes — multiple handlers, isolated dispatch | No envelope/metadata beyond the event; fine for now |
| Decision policies (config-sourced) | `AgentPolicy`, `SpawnPolicy`, `HealPolicy`, `RetryPolicy`, `LoopGuard`, `BashSafetyPolicy`, `SandboxPolicy`, … — `core/policies/` | Yes — construct + pass in / subclass | Host-agnostic already; hardened for reuse |
| LLM providers | `LLMProvider` ABC (`llm/provider.py`); injected via `Runtime.set_llm` | Yes — implement ABC | Natural plugin shape (entry-point pattern) |
| CLI / state surfaces | `cli/terminal.py`, `cli/state.py` (`StateWriter`), `cli/present.py` | Code-level | No discovery — a plugin offering its own CLI/view is invisible today |

Relevant supporting docs already in repo:

- `docs/api/policies.md` — policies are "reused by plugin hosts (MCP /
  extension) without coupling to the harness core"
- `docs/platform-evaluation.md` — portability thesis; recursion hosts'
  extension APIs; OpenCode's `tool.execute.before/after` preview of what a
  plugin contract looks like on a host
- `docs/gap-analysis.md` — P1 flag: "no LLM-spawnable custom agents" (a
  *runtime* plugin gap)

## The plugin-centric target (working definition)

A plugin is a **self-describing unit of extension** with three contract
elements:

1. **Manifest** — name, version, what it contributes (tools / policies /
   agent classes / event handlers / LLM providers / CLI views), and any
   declared dependencies or conflicts.
2. **Activation** — a load step (static, at runtime construction) and/or an
   activate step (mid-run), returning a health result so the host can accept,
   warn, or refuse.
3. **Contributions** — one or more registrations against existing seams,
   expressed through the *same* public register calls a host user would use
   (no new "plugin-only" API surface).

Desired properties:

- **Uniform loading.** A plugin directory / entry point is scanned; each plugin
  is loaded and its contributions are wired. No editing `registration.py`.
- **Precedence + replace.** Re-register-by-name already replaces (policy
  registry). Make override semantics explicit per seam (later overrides? refuse
  core-overrides unless marked?).
- **Containment.** A crashing/ill-behaved plugin fails *its* activation or
  contribution, not the run loop. Registrations must never weaken safety
  invariants by accident (spawn caps, loop detection, result handles).
- **Introspection.** Installed plugins are queryable (`Runtime` should answer
  "what is installed" for tools/policies/agents), feeding `status`,
  `docs/api/`, and diagnostics.
- **Out of the box: the core IS thin.** Default tools/policies/agents/CLI
  become the first "stdlib" plugins registered from a discovery default, so the
  difference between built-in and third-party is *where it was loaded from*,
  not *what it can do*.

## Design space / options to weigh

### A. Uniform `Plugin` interface + loader (native plugin host)

Introduce a `Plugin` protocol (manifest + `install(host)`), a loader that scans
`~/.config/dynamic-harness/plugins/` + a project `plugins/` dir (+ optional
entry-point group in pyproject), and convert the default surface into resolved
"stdlib" plugins registered through the same path.

**Pros:** one contract, one load path; the harness is unmistakably a host;
internal refactor forces every seam to be exercised through public APIs (dogfooding platform-evaluation's claims); a third-party plugin is indistinguishable from a built-in except provenance.
**Cons:** machinery before payoff — a loader, manifest schema, error/containment
policy, precedence rules, and migration of `register_default_tools` /
`register_agent_class` / policy wiring to plugin-style registration. Larger
surface to test (deterministic mock-LLM tests must not depend on plugin dirs).

### B. Shared contracts only, no loader (contracts-first)

Ship the *interface* work only: `Plugin` protocol + refine each seam so
everything presentable as a plugin *is* a typed contribution object, but leave
discovery to the user (pass a list into `Runtime`, like `set_llm`). Loader comes
later once the contracts prove stable.

**Pros:** small, low-risk, immediate value: the codebase becomes "composable
from documented extension points" without new I/O or failure modes; the policy
interface refactor already proved this pattern works.
**Cons:** not yet plugin-*centric* — no discovery, no health, no containment;
third parties still hand-wire; the "thin core" claim stays aspirational.

### C. Two worlds: native host *and* third-party host (external seam)

Pursue both the native plugin host (B→A) and the externalization thesis
(`docs/platform-evaluation.md`): define the seam once, then expose it verbatim
behind a transport (MCP server / config-driven preload) so a non-Python host
drives the same decisions. The `ReactivePolicy` interface and
`register_reactive_policy` are the existing seed.

**Pros:** maximizes reuse of the decision layer; directly answers the platform
port; single contract serving two audiences.
**Cons:** scope sprawl; transport adds auth/serialization concerns ("0 vs null"
config conventions already show the attention such compatibility requires);
risks conflating "the core is a host" with "every host can drive our core".

## Open questions to resolve before implementation

1. **Name collision with the platform thesis.** "Plugin-centric" in this repo
   means the harness's own extension model. `docs/platform-evaluation.md` uses
   "plugin" for *other* hosts. Is the internal work the enablement for the
   external (option C), or a project in its own right (option A/B)? What does
   success look like for each?
2. **Manifest schema scope.** V1 minimal (name/version/contributions) or richer
   (dependencies, conflicts, config defaults, permissions)? Over-spec vs
   churn trade-off.
3. **Containment policy.** What does a failing plugin do — refuse install with
   a report, isolate to a disabled state, or crash loudly? Where do health
   results surface (`status` tool? terminal? state files?)?
4. **Safety boundary.** Can a plugin replace `LoopGuard`, `SpawnPolicy`, or the
   mutator set? Since safety invariants are the differentiator, define what is
   *overridable* vs *frozen*. Default bias: policies replaceable, safety
   invariants frozen, tools additive, agent classes additive.
5. **Config interplay.** Plugin behavior is config-sourced today
   (`harness.json`). Do plugins contribute their own config schema (merged at
   load) or stay code-only, consuming `harness.json` like the policies do?
6. **The stdlib conversion.** Is converting the built-in tools/agents/policies
   into "default plugins" a prerequisite (dogfooding) or a later cleanup that
   risks churn? Which default-first is lowest-risk to prove the contract
   (policies, already have a registry)?
7. **Deterministic testing.** Plugin discovery introduces filesystem/IO into
   runtime construction, which mock-LLM tests currently avoid. Where is the
   discovery boundary so tests pass a plugin list explicitly?

## Investigation next steps

- [ ] Decide A vs B vs C (lean: B first — contracts; A follows if the contracts
      hold; C only if enabled by A/B decisions)
- [ ] Enumerate every current registration call site (`register_default_tools`,
      `register_agent_class`, `register_reactive_policy`, `on_*` handlers,
      `set_llm`, custom CLI) into a single canonical "what the host can accept"
      inventory
- [ ] Draft the `Plugin` protocol + one `Contribution` type per seam, using the
      existing `ReactivePolicy` interface as the reference for the shape
      (runtime.py:153 comment already names the seam)
- [ ] Read `docs/platform-evaluation.md` in full and reconcile terms
      (internal plugin vs external host plugin) into one glossary
- [ ] Spec the containment + health semantics (what a refused plugin reports,
      where it surfaces)
- [ ] Spec precedence/override rules and the frozen-safety boundary
- [ ] Choose the discovery boundary for tests (explicit list vs directory
      scan; default off in tests)
- [ ] Decide stdlib-vs-defaults conversion strategy and pick the first pilot
      seam (likely: policies → a `core/plugins/` loader with reactive registry
      as first contribution)
- [ ] Flag relations to G8 (budget/cost — another plugin-shaped mechanism) and
      the P1 "no LLM-spawnable custom agents" gap