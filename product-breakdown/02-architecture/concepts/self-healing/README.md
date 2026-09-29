---
title: Self-Healing Agents
summary: How the runtime recovers an agent run that did not produce its intended deliverable without restarting the whole task — salvaging healthy work while n…
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
- Agent states/run loop → [agent-lifecycle/](../agent-lifecycle/README.md)
- Parent failure choices → [delegation-model/failure-handling.md](../delegation-model/failure-handling.md)
- Artifact/commit mechanics → [artifact-system/](../artifact-system/README.md)

See `../../../../docs/api/agent.md`, `runtime.md`, `tools.md`.

## Contents

<!-- pb:index:start -->
- **INFO-045** [Configuration & Integration](configuration.md) — A conservative budget beside the existing safety knobs
- **INFO-046** [Design Rationale](design-rationale.md) — Self-healing recovers an agent run that did not produce its intended deliverable without restarting the whole task. The goal is to salvage healthy wor…
- **INFO-047** [Implementation Plan](implementation-plan.md) — Rely on deterministic Runtime logic, not model compliance. the rot discriminator. because the model keeps refusing the tool, escalate rather than loop…
- **INFO-048** [Layer 3 — Fresh Worker](layer-fresh-worker.md) — Trigger: context rot — fired, reached, wall-clock timeout, or repeated Layer-1 misses. Resuming here would replay the poisoned context. Instead, re-de…
- **INFO-049** [Layer 2 — Parent Heal](layer-parent-heal.md) — At the delegation boundary the runtime already runs its own automatic recovery. Separately, a parent can drive recovery explicitly via the tool — choo…
- **INFO-050** [Layer 1 — Resume-once (the escape hatch)](layer-resume-once.md) — Primitive: / (runtime.py:115-137, agent.py:163-171). Appends a user message and re-runs on the same agent — has no guard against a prior terminal stat…
- **INFO-051** [The Layered Policy](layered-policy.md) — Wall-clock timeouts never self-heal. A timed-out agent ( is false > for it — the context is fine, the run simply exhausted its wall-clock budget) > is…
<!-- pb:index:end -->
