# Sibling Collaboration (B-curated): Common-Parent Scoping

How to enable real collaboration (B) while containing its cons, by **constraining
peer-to-peer communication to siblings that share a common parent** ("children of
one parent form a team"). Decisions: [AD-002](../decisions/AD-002.md).

## The key idea
"Team membership" is defined by **shared parentage** — a concept the runtime
already tracks (`task.parent_id`, the task graph). No new structural entity: a
collaboration group *is* the parent-owned subtree. Communication is allowed only
between agents that share a parent, and the parent is that group's natural
authority (authorize, observe, revoke channels).

## Enabling mechanism — mostly plumbing that already exists
The delivery machinery is already present and used by `converse`:
- `converse` tool → `continue_with_input(agent_id, message)` (`tools/agents.py:306`,
  `agent.py:683`) — a child pushes a message to a live sibling; wakes it.
- `submit_input` / `_inject_queue` / `_inject_event` (`agent.py:1246-1267`) —
  queued while busy; interrupts a child waiting on its own children.
- `get_other_agent` (`agent.py:1500`) — address resolution; today ANY agent,
  needs scoping.
- Status gates (conversable = completed/running) (`policies/permissions.py:51`) —
  eligibility for receiving messages.
- Streaming `[child settled]` events (`agent.py:1374/1410/1461`) — parent-aware
  event hook where sibling channels attach.

So **B is not a from-scratch build** — it is (1) a new *scope rule* on who may
message whom, (2) a *delivery/budget policy*, and (3) *loop detection + parent
visibility* around exchanges. `converse` already proves a live child can be
pushed mid-run.

## Collaboration patterns this unlocks
- **Handoff** — A produces an intermediate artifact, sends `artifact_id` to B.
- **Critique / peer review** — B reviews A's artifact and returns feedback; A
  revises. Internal QA *without* polling the parent's context.
- **Combine / merge** — children merge partial results before reporting to the
  parent (reduces parent synthesis load).
- **Ask a sibling for help** — A blocked on missing knowledge a peer has (the
  documented `ask` pattern, peer-to-peer instead of human/parent).
- **Coordination on a shared target** — children on parts of one subsystem
  exchange updates to avoid conflicting writes.
