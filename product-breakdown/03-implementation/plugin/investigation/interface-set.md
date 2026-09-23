---
title: "Plugin Direction — Target Common-Interface Set (~7)"
category: investigation
parent: "README.md"
summary: >
  The seven interfaces that constitute the target; success means the count
  holds while couplings are removed.
---

# The count — target common-interface set (~7)

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
