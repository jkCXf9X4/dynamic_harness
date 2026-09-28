# Collaboration Setting — Enforcement Points and Config

Sections 6–7 of the collaboration-setting spec. Index: [README.md](README.md).

## 6. Enforcement points in the codebase
- Capability distribution — `core/agent.py` — `Agent.collaboration:
  CollaborationCapability` (member+founder facets).
- Scope rule (message) — `core/agent.py:get_other_agent` — eligibility = direct
  child OR introduced sibling.
- Team registry / lifecycle — `core/runtime.py` — `create_team()`,
  `team_add_member()`, `team_write()`, `team_msg()`, `settle_team()`,
  `disband_team()`.
- Norms + sanctions + loops — `core/policies/team.py` — new `TeamPolicy` (caps,
  ladder, pair counter).
- Workspace path scoping — `core/policies/workspace.py` — resolve under
  `team.workspace_root`; append-only enforcement.
- Team tools — `core/tools/team.py` + `registration.py` — `workspace_*`,
  `introduce`, `team_charter`, `team_status`, `disconnect`, `disband_team`;
  `converse` scope expansion.
- ToolContext plumbing — `core/tool_context.py` — expose team-scoped
  reads/writes/messages.
- Config — `config.py` + `harness.json` — `collaboration:` section (defaults,
  "cap off" `0`/`null` convention).
- Prompt / heuristic — `prompts.py`, `agent_system_prompt.txt` — workspace-bias +
  equivocal-vs-uncertain rule §5.1.
- Arbitration / verify — existing `VerifyPolicy`, `escalate`, `kill`/`resume` —
  wired to team lifecycle.
- Permissions — `policies/permissions.py` — introduce/team tools founder-gated
  (`self.children`); member tools scoped.

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
Follows the repo convention: `0`/`null` "caps off". `enabled: false` returns the
runtime to today's behavior (stream_children fan-out only).
