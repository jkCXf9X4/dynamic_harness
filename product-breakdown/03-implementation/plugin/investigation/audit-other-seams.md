---
title: "Plugin Direction — Remaining Seams Breadth Audit + Trim"
category: investigation
parent: "README.md"
summary: >
  Event bus, LLM provider, agent-class registry, data types, and the trimmed
  target.
---

# 3. Event bus, LLM, agent registry, data types

## Event bus (`EventBus` + payload types)

Consumers: `Runtime.on_*` handling, `Harness` (`on_report`/`on_failure`/
`on_activity`), CLI (`events.jsonl` via StateWriter), telemetry/activity
emission from Agent. Handlers are isolated by `_dispatch`; `handler_counts()`
now exposes the seam for the canonical map. Breadth: 5 event kinds, each a
typed payload — no change needed.

## LLM provider (`LLMProvider` ABC)

Consumers: Runtime (`set_llm`/injection), Agent (`generate_with_tools`,
retry/compress paths), `Harness._configure_llm`, benchmark/CLI wiring. One
ABC, one injection point — clean seam, no change.

## Agent-class registry

Consumers: Runtime (`delegate` via `agent_type`), `tools/agents.py` delegate
tool. Bare dict today; the canonical map surfaces it. No change needed now.

## Data types

Pure Pydantic models consumed across all layers (`Task`, `ReportPayload`,
`Artifact`, `Commit`, `AgentOutcome`, event payloads). No host logic inside —
the cleanest seam; no change.

## Trimmed target (what this audit proposes)

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
