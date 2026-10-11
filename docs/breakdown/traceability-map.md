# Traceability Map — dynamic_harness

Seed map linking **Claim/Need → Decision → Realizing artifact/evidence**, created 2026-09-21 from `.dynamic-harness/260921_153611_b5cb/artifacts/breakdown_structure_critical_review.md` (draft traceability map). It is the repo-level V-model closure ("every output traced to a requirement", VISION). Update it whenever a claim, decision, or artifact changes.

## How to read this map

- Hand-written by documented repo choice. `pb.toml` sets `traceability = ""` (no generated map); `README.md` says it covers claims and needs, not only records.
- Columns: Claim/Need → Decision → Realizing artifact/evidence.
- Decision column cites live AD-* record IDs. Records live in `docs/archive/archive.zip`, read via `pb archive read <ID>`.
- DL-1…DL-17 are retired. Their home is the tombstone `deprecated/decision-log.md` (read via `pb archive read deprecated/decision-log.md`). A row with no AD successor cites that tombstone.
- Paths are post-move canonical homes. RL-* are root/docs/reference paths that stay in place.

| Need / Claim | Decision(s) | Realizing artifact / evidence |
|--------------|-------------|-------------------------------|
| "Maximize quality, minimize cost" | `deprecated/decision-log.md` (fresh-context economics) | `README.md`, `00-intent/VISION.md`, `02-architecture/concepts/delegation-model/README.md` (cost tables) |
| "Verify every child; never synthesize from assumed results" | `deprecated/decision-log.md` (15288 VERIFY / V-model), `deprecated/decision-log.md` (golden rule) | `docs/references/15288_rationale.md`, `02-architecture/methodology/README.md` P3, `04-verification/gap-analysis/README.md` G1 (open — verify not mechanized) |
| "Agents isolated, shallow contexts" | `deprecated/decision-log.md` (actor model) | `02-architecture/concepts/agent-lifecycle/README.md`, `02-architecture/concepts/delegation-model/README.md`, `00-intent/competitive-differentiation/README.md` |
| "Parents consume summaries, not raw context" | `deprecated/decision-log.md` (artifact-driven + progressive disclosure) | `02-architecture/concepts/artifact-system/README.md`, `04-verification/gap-analysis/README.md` G3/G4 RESOLVED |
| "Reproducible, auditable runs" | `deprecated/decision-log.md` (git-like provenance) | `02-architecture/concepts/artifact-system/README.md` §Commits, `01-product/requirements/README.md` FR-6, run overview files documented in `05-operation/guides/getting-started/output.md` |
| "Children collaborate without parent relay" | `AD-001` (reject A), `AD-002` + `AD-003` (topic channels) | `06-evolution/investigations/communication-structures/{INVESTIGATION,FINDINGS,RESULTS}.md`, `plan/`, `context-injection-design.md` |
| "Extensible / replaceable components" | `AD-007` (interface economy), `deprecated/decision-log.md` (policy extraction) | `06-evolution/investigations/plugin/investigation/README.md`, `06-evolution/investigations/platform-evaluation/README.md` |
| "Recover from failure without grinding" | `deprecated/decision-log.md` (self-healing) | `02-architecture/concepts/self-healing/README.md`, `00-intent/competitive-differentiation/README.md`, `04-verification/gap-analysis/README.md` G2 RESOLVED |
| "Choose collaboration topology on evidence" | `deprecated/decision-log.md` (benchmark-driven verification) | `06-evolution/investigations/communication-structures/{RESULTS.md, metrics-cells.json, FINDINGS.md}` |
| "Composable CLI for automation" | `deprecated/decision-log.md` (CLI-first minimal) | `01-product/requirements/README.md` FR/NFR, `06-evolution/backlog.md` |
| "Delegate when it pays; right-size ceremony" | `deprecated/decision-log.md` (golden delegation rule) | `02-architecture/methodology/README.md`, `3rd_party/agent_methods_and_tools/src/agent_methods/methods/delegation-guidelines/SKILL.md`, `3rd_party/agent_methods_and_tools/src/agent_methods/methods/tool-motivations/SKILL.md` |
| "Child autonomy safe via intent" | `deprecated/decision-log.md` (mission-command briefs) | `3rd_party/agent_methods_and_tools/src/agent_methods/methods/mission-command/SKILL.md`, `02-architecture/concepts/delegation-model/README.md`, `03-implementation/` (BriefPolicy in `src/dynamic_harness/core/policies/brief.py`) |
| "Definition state stays navigable and canonical, not accumulated" | `AD-009` (node model) | `README.md` (Node Model), `docs/references/information_hygiene.md` |

## What Is Not Yet Traced (open work)

- **REQ-1..15** (collaboration spec, `06-evolution/investigations/multi-agent-coordination/collaboration-setting/README.md`) — link to AD records and the team-charter/channel machinery once the comms implementation lands (see `06-evolution/roadmap.md`).
- **G1–G13** (`04-verification/gap-analysis/README.md`) — link each gap to the decision that caused it and the IMP that fixes it.
- **VISION pillars / success criteria** (`00-intent/VISION.md`) — trace each pillar/criterion to its realizing artifact.

These seed rows are the highest-value links from the review. Completing the map is an ongoing maintenance duty, not a one-time artifact.
