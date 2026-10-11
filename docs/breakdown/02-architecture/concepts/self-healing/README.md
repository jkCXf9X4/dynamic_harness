---
title: Self-Healing Agents
summary: How the runtime recovers an agent run that did not produce its deliverable without restarting the task — salvaging healthy work, never grinding a poisoned context
---

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
- Agent states/run loop to [agent-lifecycle/](../agent-lifecycle/README.md)
- Parent failure choices to [delegation-model/failure-handling.md](../delegation-model/failure-handling.md)
- Artifact/commit mechanics to [artifact-system/](../artifact-system/README.md)

See `../../../../docs/api/agent.md`, `runtime.md`, `tools.md`.

## Contents

<!-- pb:index:start -->
<!-- GENERATED FILE — do not edit. Regenerate with pb-registers. -->
- **INFO-045** [Configuration & Integration](configuration.md) — A conservative budget beside the existing safety knobs
- **INFO-046** [Design Rationale](design-rationale.md) — Self-healing recovers an agent run that did not produce its deliverable without restarting the task, salvaging healthy work while never grinding a poisoned context
- **INFO-047** [Implementation Plan](implementation-plan.md) — Rely on deterministic Runtime logic, not model compliance; the rot discriminator bounds cost and retries, and a missing deliverable escalates rather than loops
- **INFO-048** [Layer 3 — Fresh Worker](layer-fresh-worker.md) — Layer 3 fresh worker: on context rot, re-delegate a fresh agent over the same task, injecting the failure reason and pointing at on-disk artifacts
- **INFO-049** [Layer 2 — Parent Heal](layer-parent-heal.md) — Layer 2 parent heal: a parent drives recovery explicitly via the resume tool, choosing resume or fresh per child, sharing the same heal budget
- **INFO-050** [Layer 1 — Resume-once (the escape hatch)](layer-resume-once.md) — Layer 1 resume-once: re-run the same agent via continue_with_input after a blunt stop with no deliverable, exactly once
- **INFO-051** [The Layered Policy](layered-policy.md) — Five recovery layers (in-loop, resume-once, parent heal, fresh worker, escalate) chosen by a rot discriminator; wall-clock timeouts never self-heal
<!-- pb:index:end -->
