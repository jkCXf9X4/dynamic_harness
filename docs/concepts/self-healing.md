---
title: "Self-Healing Agents"
category: concept
summary: >
  How Dynamic Harness recovers from agent failure in normal use. A layered,
  diagnosis-driven policy that resumes a healthy context, starts fresh on a
  poisoned one, and escalates the rest — implemented as deterministic Runtime
  logic, not prompt suggestions.
related:
  - api/agent.md
  - api/runtime.md
  - api/tools.md
  - concepts/agent-lifecycle.md
  - concepts/delegation-model.md
  - concepts/artifact-system.md
---

# Self-Healing Agents

Self-healing is the ability of the runtime to recover an agent run that did not
produce its intended deliverable, without restarting the whole task from
scratch. The goal is to **salvage healthy work** while **never grinding a
poisoned context**.

## The Design Trap

The codebase philosophy is *"disposable workers — state lives in artifacts, not
agent memory."* This is a deliberate argument against rescuing bad contexts.
Fresh context is cheap (delegation overhead ~3K tokens) and fixes context rot;
in-memory context is expensive and rots.

So self-healing must **not** be a blanket "always resume the same agent." It is
a **diagnosis-driven policy**:

- If the agent stopped because of a *blunt, recoverable* mistake on an otherwise
  healthy context → **resume the same agent** (cheap, salvages its context).
- If the agent stopped because its *context itself is the problem* (repeated
  identical calls, max iterations) → **start a fresh worker** over the same task
  (freshness fixes rot; on-disk artifacts preserve progress).
- If the failure is structural (task impossible, bad spec) → **escalate**.

## Why Deterministic Runtime Logic, Not Prompt Text

The system prompt already *tells* the model to prune/restore/compress and to
verify children. Measured behavior: the model rarely complies (e.g. it almost
never calls `prune` on the manyfiles task, and token use balloons to 200–680K).

A self-healing guarantee cannot depend on model obedience. The reliable value
comes from Layers 1–3 being **deterministic Runtime machinery** that re-enters
the agent loop from code, using prompt nudges only as *input* to that machinery.

## The Layered Policy

| Layer | Trigger (diagnosis) | Action | Loop budget |
|-------|--------------------|--------|-------------|
| 0. In-loop | tool error / verification mismatch | agent re-reads & re-calls built-in tool results | natural, bounded |
| 1. Resume-once | blunt stop, healthy context (prose answer, forgot artifact, single recoverable error) | `continue_with_input` with a focused nudge | 1 shot |
| 2. Parent heal | child failed, cause clearable | parent `resume()` tool: resume the same child (blunt) or a fresh worker (rot), with the failure reason + a parent note | `max_resumes` / `max_fresh_retries`, per child |
| 3. Fresh worker | context rot (repeated-call, max-iterations, poison) | re-delegate a fresh agent, inject failure reason + existing artifact IDs | 1 retry |
| 4. Escalate | structural / impossible | escalate to parent | never |

### Layer 0 — In-loop correction

No extra machinery. The agent sees tool results (errors, empty reads, failed
verification) and re-calls. This works today and needs only good tool feedback
and observation messaging.

### Layer 1 — Resume-once (the escape hatch)

Primitive: `Agent.continue_with_input(msg)` / `Runtime.run(msg, root_agent=...)`
(runtime.py:115-137, agent.py:163-171). Appends a user message and re-runs
`_run_loop()` on the **same** agent — the `_run_loop` has no guard against a
prior terminal status, so it resumes cleanly.

Trigger: single agent terminated *without* a normal report, or terminated with
a report but produced no deliverable (missing output file / empty artifact),
where its context is small and shows no repeated-call signature. It runs
**exactly once**. A second miss flips the diagnosis to rot.

The deliverable check is implemented in `Runtime._has_deliverable()`: if
`Runtime.run(..., expected_outputs=[...])` declared files the task must write,
they must all exist on disk; otherwise a report must declare `files_written` /
`artifact_ids`. A prose-only report (no files, no artifacts) is not a
deliverable and triggers Layer 1.

Example from practice: the optimizer generation agent answered in prose instead
of writing its JSON artifact — clean context, one turn, simply needed the nudge
"write the file now." Layer 1 fixes this for ~one extra LLM turn.

### Layer 2 — Parent heal

At the delegation boundary, the runtime already runs its own automatic recovery.
Separately, a parent can *drive* recovery explicitly via the `resume` tool —
the parent chooses when and how to recover a child that failed or finished
without a deliverable, instead of relying only on the automatic policy:

- `resume(agent_id, note, strategy="automatic")` applies the same blunt-vs-rot
  diagnosis as Layers 1/3: **blunt** (healthy context, single clearable error)
  resumes the *same* child via `Runtime.resume(id, message, parent=...)`,
  salvaging its partial artifacts and context; **rot** (repeated calls, safety
  stop) spawns a fresh worker over the same task via `_fresh_restart`.
- `strategy` lets the parent force either path: `"resume"` (refused when the
  context is rotted — replaying a poisoned context would repeat the failure) or
  `"fresh"` (clean restart even on a blunt miss).
- The parent's `note` is appended to the resume/fresh prompt as a targeted
  corrective instruction ("you missed the deliverable file", "look in X").

Both layers consume the *same* heal budget as automatic self-heal
(`max_resumes` / `max_fresh_retries`, per child), so parent-driven and
runtime-driven recovery cannot stack unboundedly. Escalated and deliberately
killed children are never resumed. Parents inspect the `heal` block on each
`status` snapshot (diagnosis + counts + recoverable flag) to decide whether to
resume a child or re-delegate it fresh themselves.

### Layer 3 — Fresh worker

Trigger: **context rot** — `repeated_call_limit` fired, `max_iterations`
reached, wall-clock timeout, or repeated Layer-1 misses. Resuming here would
replay the poisioned context. Instead, re-delegate a fresh agent over the same
task, but:
1. inject the prior failure reason into the new description, and
2. point it at on-disk artifacts the dead worker already produced.

This reconciles with disposable-worker economics: freshness fixes rot, disk
preserves partial progress. Budget: one retry; a second failure escalates.

### Layer 4 — Escalate

Structural or repeated failure → escalate to the parent / caller. Never grind.

## The Rot Discriminator

The Runtime already tracks both signals for free:

- **Blunt** → `task failed/completed` with a *specific recoverable error*,
  low iteration count, no repeated-call hit.
- **Rot** → `repeated_call_limit` fired, or `max_iterations`/timeout reached,
  or high iteration count with unchanged output.

The discriminator maps observed state → layer, monotonically:
`Layer 1 → (miss) → Layer 3 → (miss) → Layer 4`, bounded per task.

## Configuration

A conservative budget beside the existing safety knobs:

```jsonc
{
  "self_heal": {
    "mode": "on",            // on | off
    "max_resumes": 1,        // Layer 1 budget (same-agent resumes)
    "max_fresh_retries": 1   // Layer 3 budget (fresh-worker redelegates)
  }
}
```

## Integration Points

- **Choke points** — wrap the two places that `await` a run and can act on its
  non-report outcome:
  - `Runtime.run` root boundary (runtime.py:136)
  - `run_delegate_tool` / parent boundary (agent.py:601)
- **`heal(agent, diagnosis)`** — inspects `agent.outcome` + safety counters,
  picks the layer, re-enters the loop with the correct nudge/injection.
- **Escapement** — track heal attempts per task so the layer sequence is
  monotone and bounded.
- **Observability** — emit each heal as an `ActivityEvent` for the CLI/UI.

## Known Caveats

- Prompt-instructed behavior (Layer 0) is weak — the model barely calls
  `prune`. Rely on deterministic Runtime logic, not model compliance.
- The primary risk is cost / unbounded retries — controlled by the budget and
  the rot discriminator.
- A resume re-executes from the current context; if the deliverable is missing
  because the model keeps refusing the tool, escalate rather than loop forever.

## Implementation & Test Plan (Layer 1 + Rot Discriminator)

Implementation order:

1. **`heal()` helper + escapement** — per-task heal counter; expose on Agent.
2. **Rot discriminator** — compute blunt-vs-rot from `outcome.failure`,
   `repeated_call_limit`, iteration count, and existing artifact presence.
3. **Wire Layer 1 into `Runtime.run` (root)** — on non-report termination with
   a missing deliverable and a healthy context, resume once with a generated
   nudge; else pass through.
4. **Wire Layer 3 into the parent boundary** — on rot (or a second Layer-1
   miss), re-delegate fresh with failure reason + artifact IDs; then escalate.
5. **Default budget conservative** — `max_resumes: 1`, `max_fresh_retries: 1`.

Test matrix (mock LLM, deterministic):

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
