---
title: "Plugin Direction — Current Interface Inventory"
category: investigation
parent: "README.md"
summary: >
  The seams that exist today and the observed couplings that make them
  incidental rather than minimal.
---

# What already exists (interface inventory)

## The seams today

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

## Observed couplings worth reviewing (the decoupling target)

- **`ToolContext` is a wide façade.** It exposes env, locks, llm, message
  buffer, usage, artifact/result stores, plan/checkpoint, compress/prune/
  restore, *and* authority actions (report/escalate/fail/kill/status/converse),
  plus direct reach into private state (`record_archived_artifact` appends to
  `agent._archived_artifact_ids`, `tool_context.py:104-109`). Every tool fn
  receives all of this; nothing restricts a file tool from pulling an agent's
  message buffer. Minimal interface = **facet the façade** (or accept one
  deliberately-broad façade and document it — decision needed).
- **`ToolContext.compress` builds its compression prompt inline**
  (`tool_context.py:126-136`) — policy-ish logic living in an interface object,
  not in a policy.
- **Tools import policies/task types directly.** `tools/agents.py` imports
  `policies.disclosure.DisclosurePolicy` and `policies.permissions.
  ToolPermissionPolicy`; `tools/context.py` imports `task.ActivityEvent`.
  Policies are host-agnostic, so this is not a layering violation per se — but
  it is an *un-centralized* decision path (policy applied inside a tool, not
  delegated by the registry). Worth an explicit ruling: is policy application
  registry-delegated (single path) or tool-embedded (many paths)?
- **`ToolContext.status`/`kill`/`continue_with_input` reach the agent actor
  directly** (`tool_context.py:199-228`) — coupling the tool façade to live
  agent lifecycle. Fine while ToolContext is the only door; a narrow-interface
  pass should list exactly which tools use which doorway methods.
