# Collaboration Setting — Acceptance, Non-Goals, Open Items

Sections 8–10 of the collaboration-setting spec. Index: [README.md](README.md).

## 8. Acceptance criteria (tests)
- **AC-1** Two children spawned with the same `team.label` are members; a third
  without is **not** — `test_team_membership_boundary`.
- **AC-2** A member's `workspace_write` outside `workspace_root` is refused —
  `test_workspace_scoping`.
- **AC-3** Indirect sibling (`converse` across teams / non-introduced) is refused
  — `test_message_scope_rule`.
- **AC-4** A pair exceeding `max_messages_per_pair` without a settle marker
  escalates L0→L3 — `test_graduated_sanctions`.
- **AC-5** Unresolved dispute after the pair budget routes to the founder once
  (`resolve_as=dispute`) — `test_arbitration_routes_to_founder`.
- **AC-6** Team settlement runs `VerifyPolicy.check` against `charter.acceptance`;
  missing terms → nudge/fresh — `test_charter_verify_on_settle`.
- **AC-7** Founder `report`/settle disband-keeps commits/artifacts of settled
  members — `test_disband_preserves_commits`.
- **AC-8** A leaf (no `self.children`) cannot use founder tools —
  `test_founder_requires_children`.
- **AC-9** Member instructions are advisory: a sibling message can be
  ignored/challenged without penalty state — `test_advisory_messaging`.
- **AC-10** Append-only: an existing workspace path cannot be overwritten, only
  appended/new — `test_append_only`.
- **AC-11** Deterministic with mocked LLM providers (project convention).

## 9. Non-goals (explicit)
- **No sibling-direct filesystem** beyond the team workspace.
- **No global message bus** — addresses resolve only to children + introduced
  siblings.
- **No peer-chair agent** by default (edge case only: very large groups).
- **No facilitator agent** — L1 is policy/code, L2 is the founder's authority.
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
      messages vs a new `TeamMailbox` (lean: reuse `_inject_queue`).
- [ ] Config default: `enabled` (opt-in) vs `stream_children`-style flag name;
      keep round-trip compatible with existing harness.json files.
