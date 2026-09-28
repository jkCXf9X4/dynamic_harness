# Collaboration Setting — Behavioral Rules

Section 5 of the collaboration-setting spec. Index: [README.md](README.md).
Operationalizes the channel + facilitation decisions.

## 5.1 Channel selection — workspace first, message on equivocality
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

## 5.2 Cadence — settle-then-yield for the workspace
- A member persists (checkpoint/`workspace_write` with a settle marker) before it
  may send another pair-message (REQ-7).
- Asynchronous round: on entering its LLM turn, a member fetches *new* writes in
  its team workspace once ("fetch newly-settled siblings once per turn"), folding
  them as scoped summaries — the workspace analogue of `[child settled]`.

## 5.3 Graduated sanctions, not instant failure (REQ-13)
- **Level 0:** observe (allowed).
- **Level 1:** warn (`[team notice]` injected) at 80% of a cap.
- **Level 2:** tighten (reduce the pair/round cap for the offender).
- **Level 3:** hard stop — pair channel closed; escalation note to founder.
- All recorded on the team object (auditable; part of monitoring, REQ-15).

## 5.4 Loop detection (REQ-9)
`pair_counts` is the per-pair exchange counter. A pair that reaches the cap
*without* a settle marker → Level 2, then Level 3. Independent of the existing
per-agent repeated-call detector (this is a *group* detector, small known edge
set).

## 5.5 Arbitration — L2 (REQ-8, REQ-14)
When a dispute reaches the founder:
1. Founder reads the dispute summary + the contested workspace artifact
   (pull-only, REQ-5).
2. Founder picks exactly one of: converse a corrective instruction; disconnect
   the pair; disband team (structural conflict = re-decompose); assign a fresh
   worker carrying salvage (reuse existing kill/resume machinery).
3. Resolution is appended to `message_log` + persisted (provenance).

## 5.6 Verify — charter as the mechanical G1 target
On team settlement, the founder runs `VerifyPolicy.check(body=workspace artifact
summary, acceptance=charter.acceptance)` (existing `policies/verify.py` — the G1
mechanism). Missing acceptance terms → converse/assign-fresh; met → synthesize.
This is the team's "compelling direction" made *mechanically checkable*.
