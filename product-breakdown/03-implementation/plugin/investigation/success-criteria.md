---
title: "Plugin Direction — Success Criteria"
category: investigation
parent: "README.md"
summary: >
  Six measurable criteria for the interface-economy direction.
---

# Success criteria (measurement)

1. **The count holds ≈7.** The common-interface set in
   [interface-set.md](interface-set.md) does not grow while couplings are
   removed — refactors narrow or trade shapes, never add contracts.
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
