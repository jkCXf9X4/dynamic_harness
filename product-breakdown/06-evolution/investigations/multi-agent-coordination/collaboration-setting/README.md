# Collaboration Setting (Team) — Advanced Layer Spec

Behavioral spec for the advanced collaboration layer. The core spine is simpler:
runtime `_links` (authorized peer pairs) + reuse of the existing
converse/_inject_queue delivery + artifact/result pointers
([../spine.md](../spine.md)). This spec's team-object features are policy/surfaces
on top of that spine. Maps to Hackman's five conditions per layer (nested
enterprises) and REQ-1..15. Decisions: [AD-006](../../decisions/AD-006.md).

## Contents
- [purpose-and-scope.md](purpose-and-scope.md) — what the team is (§1)
- [object-model.md](object-model.md) — Pydantic models (§2)
- [capability-facets.md](capability-facets.md) — MEMBER/FOUNDER tools + scope (§3)
- [lifecycle.md](lifecycle.md) — state transitions (§4)
- [behavioral-rules.md](behavioral-rules.md) — channel, cadence, sanctions, loops, arbitration, verify (§5)
- [enforcement-and-config.md](enforcement-and-config.md) — codebase points + config (§6–7)
- [acceptance-and-open-items.md](acceptance-and-open-items.md) — AC-1..11, non-goals, open items (§8–10)
