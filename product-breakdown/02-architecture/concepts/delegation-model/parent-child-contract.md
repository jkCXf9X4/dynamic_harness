# Parent–Child Contract

## Parent to Child

The parent provides:
- A specific, focused task description
- A role that scopes what the child cares about
- Any necessary context (file paths, conventions)
- A mission-command intent block (see `../../../../docs/references/mission_command_rationale.md`):
  `intent` (why it matters — the child's decision criterion), `end_state` (the
  desired final condition — *this is* the acceptance criteria), `constraints`
  (task boundaries and interface rules; the child's runtime token/time caps are
  auto-injected into its system prompt, so do not repeat them), and `authority`
  (the license to adapt the plan within the intent + report deviations). Passed
  via the `delegate` tool's `intent`/`end_state`/`constraints`/`authority` fields;
  rendered into the child's system prompt (compression-safe) as `[INTENT]` /
  `[END STATE]` / `[CONSTRAINTS]` / `[AUTHORITY]` blocks.

Every child also operates under a baseline mission-command clause (from the
system prompt): honor the intent, adapt within it when the situation changes, and
report any deviation and why in `report()`/`escalate()` — even when the parent
supplied only a bare description. The parent reads the child's `limits` (token
cap / wall-clock) from the delegate result and `status` to size re-delegations.

## Child to Parent

The child returns (via `report()`):
- A concrete summary of findings
- Artifact IDs pointing to files on disk
- Optional confidence score

The child's raw context is never forwarded to the parent. This is the key to
keeping parent contexts shallow.

## Roles

A role is a one-sentence scope constraint. It narrows the agent's solution space
to prevent scope creep:

```
"You are a Security Auditor. Your only concern is vulnerabilities — flag issues, do not fix them."
"You are a Test Writer. Your only concern is test coverage. Do not modify implementation code."
```

Roles serve three purposes:
1. **Scope narrowing** — prevents the agent from wandering into unrelated concerns
2. **Token efficiency** — pre-answers decisions the agent would otherwise burn turns on
3. **Quality control** — ensures specialized work is done by specialized agents
