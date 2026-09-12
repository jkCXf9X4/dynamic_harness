---
title: "Spec — Collaboration Setting (Team) Object"
category: investigation / spec
status: draft
summary: >
  Concrete behavioral spec for the collaboration-setting runtime construct: one
  distributed capability (member + founder facets) that makes every node a
  member of its parent's team and, if it has children, founder of its own. Maps
  to Hackman's five conditions per layer (nested enterprises) and REQ-1..15.
---

# Collaboration Setting (Team) — Behavioral Spec

## 1. Purpose and scope

This spec defines the **team** (the "collaboration setting"): the first-class
runtime construct a founding parent instantiates at its delegation boundary so
that interdependent children can collaborate — share findings, negotiate,
arbitrate — *without* relaying through the parent (option A, rejected).

- **Distributed capability.** Every `Agent` node carries the same
  `CollaborationCapability` with two facets: MEMBER (active iff introduced) and
  FOUNDER (active iff the node has children). Activation is structural.
- **Layer-by-layer.** A team is instantiated at any delegation boundary where
  the parent declares interdependent children. A member child that later
  delegates founds its own nested team (Ostrom #8). Same object class at every
  layer (Hackman: real team + compelling direction are the core, provided per
  layer by that layer's father).
- **Tracing.** Each requirement maps to `INVESTIGATION.md` REQ-1..15 and the
  management-theory report §7.

## 2. Object model (Pydantic, codebase conventions)

All models follow the project conventions: `from __future__ import annotations`,
Pydantic, 12-char uuid4 hex ids (`uuid4().hex[:12]`).

```python
class TeamCharter(BaseModel):
    objective: str                    # Hackman #2 — the challenging, clear goal
    why: str                          # consequence: why this matters
    acceptance: list[str]             # G1 hook: mechanical scan target

class TeamNorms(BaseModel):           # Hackman #3 — enabling structure, as policy
    max_messages_per_pair: int = 4    # REQ-6 bounded rich channel
    max_rounds: int = 1               # settle-then-yield rounds before settle
    summary_only: bool = True         # REQ-4/5: never forward content, only summaries
    append_only: bool = True          # REQ-15: provenance = distributed monitoring
    workspace_bias: bool = True       # channel rule: try workspace before messaging

class TeamStatus(str, Enum):
    forming = "forming"               # founder declared membership; charter pending
    active = "active"                 # charter posted; members may work
    arbitrating = "arbitrating"       # an unresolved dispute escalated to founder (L2)
    disbanded = "disbanded"           # founder closed the team (or parent settled)

class Team(BaseModel):
    id: str                           # uuid4().hex[:12]
    label: str | None                 # group-by-label on delegate() ("api-team")
    founder_id: str                   # the parent of this layer (authority)
    workspace_root: Path              # artifact_root/teams/<team_id> (scoped)
    members: dict[str, str]           # agent_id -> role tag (per-delegation role)
    charter: TeamCharter | None       # posted by founder (Hackman #2)
    norms: TeamNorms                  # from config, overridable by founder
    message_log: list[TeamMessage]    # bounded, summary-only, audited (REQ-15)
    pair_counts: dict[str, int]       # per-pair exchange counters (REQ-9, REQ-13)
    sanctions: list[Sanction]         # graduated sanctions ladder (REQ-13)
    status: TeamStatus = TeamStatus.forming
    created_at: datetime

class TeamMessage(BaseModel):
    id: str
    team_id: str
    sender_id: str
    recipient_id: str
    summary: str                      # REQ-4: NEVER a content payload
    pointer: str | None               # artifact path/result handle to read for content
    created_at: datetime
```

## 3. Capability facets and scope

### 3.1 MEMBER facet (universal; active iff introduced)

| Action | Tool | Scope rule |
|--------|------|-----------|
| Read team artifacts | `workspace_read` | path must resolve under `team.workspace_root` |
| Write team artifacts | `workspace_write` | append-only (REQ-13/15); same path scoping |
| List team artifacts | `workspace_list` | scoped |
| Nudge / ask a sibling | `converse(agent_id, ...)` | **scope expansion**: target must be (your child) OR (introduced sibling). Enforced in `get_other_agent` path. Message is summary-only + optional pointer (REQ-4) |
| State a dispute | `escalate(issue, context)` | existing tool; carries `resolve_as=dispute` so founder routes to L2 |
| Decline an introduction | via `introduce` refusal | no penalty (REQ-3, psychological safety) |

Member writes are **scoped to the team workspace only** — membership grants
capability, never privilege over the broader filesystem.

### 3.2 FOUNDER facet (universal; active iff `self.children` non-empty)

| Action | Tool | Notes |
|--------|------|-------|
| Form a team at delegation time | `delegate(description, ..., team=...)` | **group-by-label**: spawning ≥2 children with the same `team.label` in one turn forms a team; charter/norms passed via `team` |
| Add an edge mid-run | `introduce(agent_a, agent_b, note=...)` | dynamic ("if it deems beneficial") — a one-call context injection (REQ-4), then the founder steps out |
| Post / replace the charter | `team_charter(team_id, objective, why, acceptance)` | sets Hackman #2; the mechanical G1 acceptance target |
| Inspect team (not content) | `team_status(team_id)` | membership, charter, sanctions, open disputes — boundary signals only (REQ-5) |
| Revoke an edge | `disconnect(agent_a, agent_b, reason?)` | team composition is mutable (REQ-10) |
| Disband | `disband_team(team_id, reason?)` | closes channels + workspace; settles N/A on parent settle/kill |
| Arbitrate an unresolved dispute | `escalate` handling: converse / disconnect / disband / assign-fresh | **no new tool**: the L2 arena **is** the founder's existing authority (REQ-8, REQ-14) |

## 4. Lifecycle and state transitions

```
FORMING                       founder spawns children with team.label
   │  founder: team_charter(objective, why, acceptance)
   ▼
ACTIVE                        members work in workspace; founder absent
   │
   ├── unresolved dispute escalated with resolve_as=dispute
   │      ▼
   │   ARBITRATING             founder arbitrates once (exception): converse →
   │   │   ok?  ──> ACTIVE     disconnect → revise membership
   │   │            └──> DISBANDED (structural conflict)
   │   └── founder may also: assign fresh worker, dissolve + re-delegate
   │
   └── founder reports / settles / is killed
            ▼
DISBANDED                     straggler members cancelled as today; their
                              commits/artifacts survive (existing semantics)
```

## 5. Behavioral rules (channel + facilitation, operationalized)

### 5.1 Channel selection — workspace first, message on equivocality

Operationalized media-richness heuristic injected into the member prompt
(`prompts.py` / `agent_system_prompt.txt`):

1. **Share / store** a finding, value, constraint → `workspace_write` (lean
   medium, uncertainty).
2. **Find out** who knows / where it lives → `converse` a *pointer* (ID + why),
   then `workspace_read` (TMS retrieval; REQ-4).
3. **Reconcile** conflicting interpretations / demand revision → `converse`
   (rich medium, equivocality); bounded by `max_messages_per_pair` + `max_rounds`
   (REQ-6, REQ-9).
4. **Stalemate after the budget** → `escalate(resolve_as=dispute)` (REQ-14).

### 5.2 Cadence — settle-then-yield for the workspace

- A member persists (checkpoint/`workspace_write` with a settle marker) before it
  may send another pair-message (REQ-7).
- Asynchronous round: on entering its LLM turn, a member fetches *new* writes in
  its team workspace once ("fetch newly-settled siblings once per turn"), folding
  them as scoped summaries — the workspace analogue of `[child settled]`.

### 5.3 Graduated sanctions, not instant failure (REQ-13)

- **Level 0:** observe (allowed).
- **Level 1:** warn (`[team notice]` injected) at 80% of a cap.
- **Level 2:** tighten (reduce the pair/round cap for the offender).
- **Level 3:** hard stop — pair channel closed; escalation note to founder.
- All recorded on the team object (auditable; part of monitoring, REQ-15).

### 5.4 Loop detection (REQ-9)

`pair_counts` is the per-pair exchange counter. A pair that reaches the cap
*without* a settle marker → Level 2, then Level 3. Independent of the existing
per-agent repeated-call detector (this is a *group* detector, small known edge
set).

### 5.5 Arbitration — L2 (REQ-8, REQ-14)

When a dispute reaches the founder:
1. Founder reads the dispute summary + the contested workspace artifact
   (pull-only, REQ-5).
2. Founder picks exactly one of: converse a corrective instruction; disconnect
   the pair; disband team (structural conflict = re-decompose); assign a fresh
   worker carrying salvage (reuse existing kill/resume machinery).
3. Resolution is appended to `message_log` + persisted (provenance).

### 5.6 Verify — charter as the mechanical G1 target

On team settlement, the founder runs `VerifyPolicy.check(body=workspace artifact
summary, acceptance=charter.acceptance)` (existing `policies/verify.py` — the G1
mechanism). Missing acceptance terms → converse/assign-fresh; met → synthesize.
This is the team's "compelling direction" made *mechanically checkable*.

## 6. Enforcement points in the codebase

| Concern | File | Change |
|---------|------|--------|
| Capability distribution | `core/agent.py` | `Agent.collaboration: CollaborationCapability` (member+founder facets) |
| Scope rule (message) | `core/agent.py:get_other_agent` | eligibility = direct child OR introduced sibling |
| Team registry / lifecycle | `core/runtime.py` | `create_team()`, `team_add_member()`, `team_write()`, `team_msg()`, `settle_team()`, `disband_team()` |
| Norms + sanctions + loops | `core/policies/team.py` | new `TeamPolicy` (caps, ladder, pair counter) |
| Workspace path scoping | `core/policies/workspace.py` | resolve under `team.workspace_root`; append-only enforcement |
| Team tools | `core/tools/team.py` + `registration.py` | `workspace_*`, `introduce`, `team_charter`, `team_status`, `disconnect`, `disband_team`; `converse` scope expansion |
| ToolContext plumbing | `core/tool_context.py` | expose team-scoped reads/writes/messages |
| Config | `config.py` + `harness.json` | `collaboration:` section (defaults, "cap off" `0`/`null` convention) |
| Prompt / heuristic | `prompts.py`, `agent_system_prompt.txt` | workspace-bias + equivocal-vs-uncertain rule §5.1 |
| Arbitration / verify | existing `VerifyPolicy`, `escalate`, `kill`/`resume` | wired to team lifecycle |
| Permissions | `policies/permissions.py` | introduce/team tools founder-gated (`self.children`); member tools scoped |

## 7. Configuration

```json
{
  "collaboration": {
    "enabled": true,
    "max_messages_per_pair": 4,
    "max_rounds": 1,
    "summary_only": true,
    "append_only": true,
    "workspace_bias": true,
    "sanction_thresholds": [0.8, 0.9, 1.0],
    "default_workspace_root": null,
    "verify_on_settle": true
  }
}
```

Follows the repo convention: `0`/`null` "caps off". `enabled: false` (default?)
returns the runtime to today's behavior (stream_children fan-out only).

## 8. Acceptance criteria (tests)

| # | Behavior | Test |
|---|----------|------|
| AC-1 | Two children spawned with the same `team.label` are members; a third without is **not** | `test_team_membership_boundary` |
| AC-2 | A member's `workspace_write` outside `workspace_root` is refused | `test_workspace_scoping` |
| AC-3 | Indirect sibling (`converse` across teams / non-introduced) is refused | `test_message_scope_rule` |
| AC-4 | A pair exceeding `max_messages_per_pair` without a settle marker escalates L0→L3 | `test_graduated_sanctions` |
| AC-5 | Unresolved dispute after the pair budget routes to the founder once (`resolve_as=dispute`) | `test_arbitration_routes_to_founder` |
| AC-6 | Team settlement runs `VerifyPolicy.check` against `charter.acceptance`; missing terms → nudge/fresh | `test_charter_verify_on_settle` |
| AC-7 | Founder `report`/settle disband-keeps commits/artifacts of settled members | `test_disband_preserves_commits` |
| AC-8 | A leaf (no `self.children`) cannot use founder tools | `test_founder_requires_children` |
| AC-9 | Member instructions are advisory: a sibling message can be ignored/challenged without penalty state | `test_advisory_messaging` |
| AC-10 | Append-only: an existing workspace path cannot be overwritten, only appended/new | `test_append_only` |
| AC-11 | Deterministic with mocked LLM providers (project convention) | `test_*` all |

## 9. Non-goals (explicit)

- **No sibling-direct filesystem** beyond the team workspace.
- **No global message bus** — addresses resolve only to children + introduced
  siblings.
- **No peer-chair agent** by default (edge case only per facilitation-layer
  analysis: very large groups).
- **No facilitator agent** — L1 is policy/code, L2 is the founder's existing
  authority.
- **No charter-less teams in production** — `VerifyPolicy` treats a missing
  charter as fail (existing `require_missing_report`).
- **No bootstrap self-formation** — a node cannot add itself to a team; only the
  founder declares membership (default-deny, REQ-2).

## 10. Open items to resolve before implementation

- [ ] `team` argument shape on `delegate()` vs a separate `form_team(label,
      objective, why, acceptance)` call — pick one (spec leans: keyword arg on
      `delegate`, because it carries charter at the boundary).
- [ ] Workspace physical layout + whether `workspace_write` creates the commit
      (`Repository.commit`) or a lighter team log entry.
- [ ] Whether `converse` scope expansion is a single flag or a
      `permissions.py`-style policy class (lean: extend `ToolPermissionPolicy`).
- [ ] Cadence mechanism: reusing `_inject_queue`/`continue_with_input` for team
      messages vs a new `TeamMailbox` (spec leans: reuse `_inject_queue`, keep
      one plumbing path).
- [ ] Config default: `enabled` (opt-in) vs `stream_children`-style flag name;
      keep round-trip compatible with existing harness.json files.