# Layer 2 — Parent Heal

At the delegation boundary the runtime already runs its own automatic recovery.
Separately, a parent can *drive* recovery explicitly via the `resume` tool —
choosing when and how to recover a child that failed or finished without a
deliverable:

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
- A timed-out child is *blunt* (its context is intact), so both `"resume"` and
  `"fresh"` are legal — the parent chooses.

Both layers consume the *same* heal budget as automatic self-heal
(`max_resumes` / `max_fresh_retries`, per child), so parent-driven and
runtime-driven recovery cannot stack unboundedly. Escalated and deliberately
killed children are never resumed. A timed-out child is never *automatically*
healed, but the parent may resume it. Parents inspect the `heal` block on each
`status` snapshot (diagnosis + counts + `recoverable` flag + `resume_hint` with
explicit tool directions on a timeout) to decide whether to resume a child or
re-delegate it fresh themselves.
