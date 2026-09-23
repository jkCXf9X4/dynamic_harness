# Parent Role: Introduce, Don't Mediate

Evaluating whether the parent should **inject the child IDs** (introduce
siblings to each other) when it deems it beneficial — while *not* overseeing the
exchanges that follow. Verdict: **yes, this is the right shape of B**, and close
to fully supported by existing plumbing. Decisions:
[AD-002](../decisions/AD-002.md).

## The mechanism: `introduce`, a one-time context injection
The parent does not relay content. It performs a single cheap act — giving each
child the *other's ID plus one line of "why you might benefit"* — and steps back.
- **Static / delegation-time:** `delegate(description, collaborate_with=[...],
  intro_note=...)` sets up a team with known dependencies up front.
- **Dynamic / mid-run:** a parent tool `introduce(agent_a, agent_b, note)` when
  it spots an intersection or a blocked child asks for help. Streaming mode
  (`[child settled]`) makes this adaptive.
- After the injection, siblings use `converse`/`continue_with_input` directly —
  no parent round-trip per message.
- The parent *can* revoke a connection (one call) — team composition is mutable.

## Can the parent decide *without overseeing*? Yes — signals, not content
The parent needs no access to sibling conversations; the observable signals
already stream to it by design:
- Child status (running / completed / failed) — `status` tool, `[child settled]`.
- Child artifact *summaries* (headline / summary_200) — VERIFY reads these.
- Blocked child (`ask` for help / pointer) — `ask` / escalation events.
- Scope overlap (same files, same target) — deducible from descriptions + paths.

Reading **summaries, not content**, is exactly the boundary-spanning visibility a
manager has (weekly report, not inbox access). Hackman calls this a *real team
boundary*: the parent sees what crosses the boundary, not what happens inside.

## Why the injection is not micromanagement (and relaying was)
**Context over control (Netflix Culture Memo).** "We expect managers to practice
*context not control* — giving their teams the context and clarity needed to make
good decisions instead of trying to control everything themselves." The injected
ID + why-it-matters is pure context; the parent supplies *alignment* (directions,
roles, connections) and then expects **highly aligned, loosely coupled**
execution. Option A (rejected) *was* control: the parent approved every exchange,
creating the manager-caused latency and context pollution Hamel calls
management's "hefty tax" (HBR, "First, Let's Fire All the Managers").
