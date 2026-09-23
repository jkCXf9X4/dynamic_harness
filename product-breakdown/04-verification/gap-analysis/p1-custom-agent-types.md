---
title: "G6 — Custom agent classes cannot be spawned by the LLM"
category: meta
summary: >
  P1 (resolved): the delegate tool accepted no agent_type, so a parent in a live
  tree could not choose a registered specialist class.
parent: "README.md"
---

# G6. Custom agent classes cannot be spawned by the LLM

**Severity:** P1. **Status:** RESOLVED.

**Concept/docs:** VISION pillar 7 "parent-defined specialized agents" and
`../../05-operation/guides/custom-agents.md:40-42` ("Via the delegate() tool in
the LLM loop: `delegate(description=..., agent_type=...)`").

**Implementation (before):** the `delegate` tool schema (`tools/agents.py:25-31`)
and `run_delegate_tool` (`agent.py:797-829`) accepted only
`description`/`role`/`system_prompt`. `agent_type` was honored only by the
programmatic `Runtime.delegate`/`Runtime.run` (`runtime.py:160, 390-411`). A
parent inside a live tree could not choose a registered specialist class for its
child — the whole specialization story was reachable only from host code.

**Breaks:** `../../01-product/use-cases/embedding-and-integration.md` Scenario B
("the LLM can spawn it via `delegate(..., agent_type=...)`"), and the VISION
pillar.

**Fix direction:** add `agent_type` to the `delegate` tool schema + allow-list
registered names, or document that custom classes are a programmatic-only
feature.

**Status:** RESOLVED — `agent_type` was added to the `delegate` tool and threaded
through `ToolContext.run_delegate_tool` → `Agent.run_delegate_tool`, which
validates against `Runtime.has_agent_class` and rejects unknown names (no silent
fallback to the base `Agent`).
