# The Layered Policy

| Layer | Trigger (diagnosis) | Action | Loop budget |
|-------|--------------------|--------|-------------|
| 0. In-loop | tool error / verification mismatch | agent re-reads & re-calls built-in tool results | natural, bounded |
| 1. Resume-once | blunt stop, healthy context (prose answer, forgot artifact, single recoverable error) | `continue_with_input` with a focused nudge | 1 shot |
| 2. Parent heal | child failed, cause clearable | parent `resume()` tool: resume the same child (blunt) or a fresh worker (rot), with the failure reason + a parent note | `max_resumes` / `max_fresh_retries`, per child |
| 3. Fresh worker | context rot (repeated-call, max-iterations, poison) | re-delegate a fresh agent, inject failure reason + existing artifact IDs | 1 retry |
| 4. Escalate | structural / impossible | escalate to parent | never |

> **Wall-clock timeouts never self-heal.** A timed-out agent (`is_rot()` is false
> for it — the *context* is fine, the run simply exhausted its wall-clock budget)
> is exempt from Layers 1 and 3: the runtime must not spend the run budget again
> on its own initiative, and re-running a big task twice burns the same cap
> twice. The child is left failed, surfaced to its parent as-is, and the failure
> message carries explicit `resume(child_id, strategy="resume"|"fresh")`
> directions. The parent — not the runtime — decides whether to continue the same
> context, retry cleanly, or fold the partial work in and re-delegate.

## Layer 0 — In-loop correction

No extra machinery. The agent sees tool results (errors, empty reads, failed
verification) and re-calls. This works today and needs only good tool feedback
and observation messaging.

## Layer 4 — Escalate

Structural or repeated failure → escalate to the parent / caller. Never grind.

## The Rot Discriminator

The Runtime already tracks both signals for free:

- **Blunt** → `task failed/completed` with a *specific recoverable error*, low
  iteration count, no repeated-call hit. Includes **wall-clock timeouts**: the
  context is healthy, the budget ran out — the parent decides whether to resume
  (same context, `strategy="resume"`) or go fresh.
- **Rot** → `repeated_call_limit` fired, or `max_iterations` reached (beyond the
  wall-clock timeout), or high iteration count with unchanged output.

The discriminator maps observed state → layer, monotonically:
`Layer 1 → (miss) → Layer 3 → (miss) → Layer 4`, bounded per task.
