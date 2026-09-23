# Design Rationale

Self-healing recovers an agent run that did not produce its intended deliverable
without restarting the whole task. The goal is to **salvage healthy work** while
**never grinding a poisoned context**.

## The Design Trap

The codebase philosophy is *"disposable workers — state lives in artifacts, not
agent memory."* This is a deliberate argument against rescuing bad contexts.
Fresh context is cheap (delegation overhead ~3K tokens) and fixes context rot;
in-memory context is expensive and rots.

So self-healing must **not** be a blanket "always resume the same agent." It is a
**diagnosis-driven policy**:

- If the agent stopped because of a *blunt, recoverable* mistake on an otherwise
  healthy context → **resume the same agent** (cheap, salvages its context).
- If the agent stopped because its *context itself is the problem* (repeated
  identical calls, max iterations) → **start a fresh worker** over the same task
  (freshness fixes rot; on-disk artifacts preserve progress).
- If the agent hit its **wall-clock budget** (`safety.timeout_seconds`) → it is
  **never self-healed** (see [layered-policy.md](layered-policy.md)); the parent
  decides.
- If the failure is structural (task impossible, bad spec) → **escalate**.

## Why Deterministic Runtime Logic, Not Prompt Text

The system prompt already *tells* the model to prune/restore/compress and to
verify children. Measured behavior: the model rarely complies (e.g. it almost
never calls `prune` on the manyfiles task, and token use balloons to 200–680K).

A self-healing guarantee cannot depend on model obedience. The reliable value
comes from Layers 1–3 being **deterministic Runtime machinery** that re-enters
the agent loop from code, using prompt nudges only as *input* to that machinery.
