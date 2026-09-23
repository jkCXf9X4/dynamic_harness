# Self-Healing Agents

How the runtime recovers an agent run that did not produce its intended
deliverable without restarting the whole task — salvaging healthy work while
never grinding a poisoned context. Implemented as deterministic Runtime logic,
not prompt suggestions.

## Owns
- The design rationale (blunt vs rot, why deterministic)
- The layered recovery policy (Layers 0–4) and the rot discriminator
- Resume-once, parent heal, and fresh-worker mechanics
- Configuration, integration points, caveats, and the implementation/test plan

## Excludes
- Agent states/run loop → [agent-lifecycle/](../agent-lifecycle/README.md)
- Parent failure choices → [delegation-model/failure-handling.md](../delegation-model/failure-handling.md)
- Artifact/commit mechanics → [artifact-system/](../artifact-system/README.md)

## Contents
- [design-rationale.md](design-rationale.md) — the design trap and why deterministic machinery
- [layered-policy.md](layered-policy.md) — Layers 0–4, wall-clock exemption, rot discriminator
- [layer-resume-once.md](layer-resume-once.md) — Layer 1 detail
- [layer-parent-heal.md](layer-parent-heal.md) — Layer 2 detail
- [layer-fresh-worker.md](layer-fresh-worker.md) — Layer 3 detail
- [configuration.md](configuration.md) — heal budget config and integration points
- [implementation-plan.md](implementation-plan.md) — caveats, build order, test matrix

See `../../../../docs/api/agent.md`, `runtime.md`, `tools.md`.
