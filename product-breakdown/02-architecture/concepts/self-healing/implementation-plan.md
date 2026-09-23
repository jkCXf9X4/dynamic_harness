# Implementation Plan

## Known Caveats

- Prompt-instructed behavior (Layer 0) is weak — the model barely calls `prune`.
  Rely on deterministic Runtime logic, not model compliance.
- The primary risk is cost / unbounded retries — controlled by the budget and
  the rot discriminator.
- A resume re-executes from the current context; if the deliverable is missing
  because the model keeps refusing the tool, escalate rather than loop forever.

## Implementation Order

1. **`heal()` helper + escapement** — per-task heal counter; expose on Agent.
2. **Rot discriminator** — compute blunt-vs-rot from `outcome.failure`,
   `repeated_call_limit`, iteration count, and existing artifact presence.
3. **Wire Layer 1 into `Runtime.run` (root)** — on non-report termination with a
   missing deliverable and a healthy context, resume once with a generated nudge;
   else pass through.
4. **Wire Layer 3 into the parent boundary** — on rot (or a second Layer-1 miss),
   re-delegate fresh with failure reason + artifact IDs; then escalate.
5. **Default budget conservative** — `max_resumes: 1`, `max_fresh_retries: 1`.

## Test Matrix (mock LLM, deterministic)

| Scenario | Expected layer | Outcome |
|----------|----------------|---------|
| Prose answer, no artifact, healthy context | 1 | resume once, deliverable written |
| Repeated identical tool calls (rot) | 3 | fresh worker, no same-context resume |
| Max-iterations reached (rot) | 3 | fresh worker, inject reason |
| Recoverable child failure (clearable) | 1/3 | child healed or re-delegated once |
| Structural failure | 4 | escalate, no retry |
| Layer-1 miss twice | 3 | escalates to fresh, then no further |
| Deliverable written on first run | – | no heal, zero overhead |

Verification: unit tests in `tests/backend/` (mock LLM for determinism) + a live
smoke test of the generation-agent flakiness that motivated this design.
