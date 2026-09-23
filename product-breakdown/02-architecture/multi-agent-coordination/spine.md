# Simplicity Review: The Spine — Links + Delivery + Pointers

The collaboration-setting spec over-modeled. The advanced features (team object,
charter, norms, sanctions, workspace, arbitration ladder) are **policy layers
that can sit on a much smaller spine** — and the spine is mostly *existing
machinery*. Decisions: [AD-006](../decisions/AD-006.md).

## The spine (three primitives, all present today)
1. **Links** — ONE new structure: a runtime registry of authorized peer pairs.
   `self._links: set[tuple[str, str]] = set()` (unordered, normalized `(min,max)`).
   The *only* authorization rule: **a `link(a, b)` call is accepted iff the caller
   is the common parent of both** — `a.parent is caller and b.parent is caller`.
   No team object, no membership dict, no lifecycle FSM: membership *is* the link
   set, authorization *is* the parent-of-both check (O(1) via `target.parent`).
2. **Delivery** — reuse the existing message path: `converse` →
   `continue_with_input` → `_inject_queue`/`_inject_event`
   (`agent.py:327/683/1246`). A sibling message is just a `converse` whose
   eligibility gate becomes `(agent_a, agent_b) in self._links` (in addition to
   parent↔child). `[sibling {id}] {summary}\nPointer: {artifact_id|result_id}` —
   summary-only, pointer-carrying, exactly like initiatives already write.
3. **Content** — reuse existing pointer machinery: the recipient pulls the full
   body via `read_artifact` / `result_read`. **No workspace needed for MVP**:
   artifacts/result snapshots are already shared, immutable, display-scoped
   state; the missing piece was only *discovery* ("who produced what"), which the
   pointer provides.

Lifecycle is free: `link` edges die implicitly when the parent settles (deleting
the subtree), or via `disconnect(a, b)`; no disband ceremony needed.

## Why this composes ("scales with more advanced processes")
- **Streaming children** — a sibling message to a child waiting on children
  wakes it via the *existing* `_inject_event` wait (`agent.py:1351`).
- **Broadcast / group** — `delegate(..., team=label)` opens all-pairs links for
  that turn's labeled children (O(n²) macro over the same primitive).
- **Loop / cost control** — trivial per-link message counter; graduated warnings
  are a policy reading it (REQ-9/13).
- **MAC catalogue / adoption** — the same link edge reused as the discovery hook
  ("sibling X has artifact Y").
- **Charter + mechanical verify (G1)** — a `verify` policy inspects *pointer
  targets* at settlement — no core changes.
- **Arbitration (L2)** — the founder already holds authority;
  `escalate(resolve_as=dispute)` routes to it.
- **Nested / recursive** — authorization ("parent of both") recurses unchanged.
- **Resume / recovery** — links reference agent ids; a resumed child re-uses the
  live registry (no per-agent state to restore).

## What this removes from the spec
- Team object, `TeamStatus` FSM, membership dict, charter object as *core*,
  workspace path-values-scoping, sanctions records as core. All become optional
  policy/surfaces on top of links.
- Enforcement shrinks to: link registry + an eligibility check in one place
  (converse path) + a counter. The rest is design intent, not mechanism.

## Comparison
- New runtime state: spine = `_links` set + per-pair counter; spec = `Team`,
  `TeamCharter`, `TeamNorms`, `message_log`, `sanctions`.
- Authorization: spine = one check (caller is parent of both); spec =
  founder/member facets, team membership.
- Delivery: spine = reuse `_inject_queue`; spec = new `TeamMailbox` or reuse.
- Shared state: spine = existing ArtifactStore/ResultStore + pointers; spec =
  new scoped workspace dir.
- New files: spine = `policies/links.py` (tiny); spec = `policies/team.py`,
  `policies/workspace.py`, `tools/team.py`.
- Time to value: spine = hours; spec = days.

Recommended structure: **build the spine; mount the advanced processes as policy
layers over it** (the codebase's own pattern — see `policies/verify.py`). The
collaboration-setting spec is demoted to the advanced layer: its AC-1..11 still
hold, but as *policy-layer* acceptance on top of the spine.
