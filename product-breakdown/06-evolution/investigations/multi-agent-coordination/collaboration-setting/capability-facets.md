# Collaboration Setting — Capability Facets and Scope

Section 3 of the collaboration-setting spec. Index: [README.md](README.md).

## 3.1 MEMBER facet (universal; active iff introduced)
- Read team artifacts — `workspace_read` — path must resolve under
  `team.workspace_root`.
- Write team artifacts — `workspace_write` — append-only (REQ-13/15); same path
  scoping.
- List team artifacts — `workspace_list` — scoped.
- Nudge / ask a sibling — `converse(agent_id, ...)` — **scope expansion**: target
  must be (your child) OR (introduced sibling), enforced in `get_other_agent`.
  Message is summary-only + optional pointer (REQ-4).
- State a dispute — `escalate(issue, context)` — carries `resolve_as=dispute` so
  the founder routes to L2.
- Decline an introduction — via `introduce` refusal — no penalty (REQ-3,
  psychological safety).

Member writes are **scoped to the team workspace only** — membership grants
capability, never privilege over the broader filesystem.

## 3.2 FOUNDER facet (universal; active iff `self.children` non-empty)
- Form a team at delegation time — `delegate(description, ..., team=...)` —
  **group-by-label**: spawning ≥2 children with the same `team.label` in one turn
  forms a team; charter/norms passed via `team`.
- Add an edge mid-run — `introduce(agent_a, agent_b, note=...)` — a one-call
  context injection (REQ-4), then the founder steps out.
- Post / replace the charter — `team_charter(team_id, objective, why, acceptance)`
  — sets Hackman #2; the mechanical G1 acceptance target.
- Inspect team (not content) — `team_status(team_id)` — membership, charter,
  sanctions, open disputes (boundary signals only, REQ-5).
- Revoke an edge — `disconnect(agent_a, agent_b, reason?)` — composition is
  mutable (REQ-10).
- Disband — `disband_team(team_id, reason?)` — closes channels + workspace;
  settles N/A on parent settle/kill.
- Arbitrate an unresolved dispute — `escalate` handling: converse / disconnect /
  disband / assign-fresh — **no new tool**: the L2 arena **is** the founder's
  existing authority (REQ-8, REQ-14).
