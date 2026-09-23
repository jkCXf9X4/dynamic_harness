# Collaboration Setting — Object Model

Section 2 of the collaboration-setting spec. Index: [README.md](README.md).

All models follow project conventions: `from __future__ import annotations`,
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
