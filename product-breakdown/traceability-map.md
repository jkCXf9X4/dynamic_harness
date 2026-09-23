# Traceability Map — dynamic_harness

Seed map linking **Claim/Need → Decision Record(s) → Realizing artifact/evidence**, created 2026-09-21 from `.dynamic-harness/260921_153611_b5cb/artifacts/breakdown_structure_critical_review.md` (draft traceability map). **This is a seed to be maintained:** it is the repo-level V-model closure ("every output traced to a requirement", VISION), and it must be updated whenever a claim, decision, or artifact changes — and reconciled to the ADR IDs (AD-001…) once they land in `02-architecture/decisions/`. Paths are the **post-move** canonical homes (RL-* are root/docs/reference paths that stay in place).

| Need / Claim | Decision(s) | Realizing artifact / evidence |
|--------------|-------------|-------------------------------|
| "Maximize quality, minimize cost" | DL-1 (fresh-context economics) | `README.md`, `00-intent/VISION.md`, `02-architecture/concepts/delegation-model/README.md` (cost tables) |
| "Verify every child; never synthesize from assumed results" | DL-2 (15288 VERIFY / V-model), DL-13 (golden rule) | `docs/references/15288_rationale.md`, `02-architecture/methodology/README.md` P3, `04-verification/gap-analysis/README.md` G1 (open — verify not mechanized) |
| "Agents isolated, shallow contexts" | DL-3 (actor model) | `02-architecture/concepts/agent-lifecycle/README.md`, `02-architecture/concepts/delegation-model/README.md`, `00-intent/competitive-differentiation/README.md` |
| "Parents consume summaries, not raw context" | DL-4 (artifact-driven + progressive disclosure) | `02-architecture/concepts/artifact-system/README.md`, `04-verification/gap-analysis/README.md` G3/G4 RESOLVED |
| "Reproducible, auditable runs" | DL-5 (git-like provenance) | `02-architecture/concepts/artifact-system/README.md` §Commits, `01-product/requirements/README.md` FR-6, run overview files (`agents.txt`, `agent_tree.json`, `stats.json`, `events.jsonl`, `index.jsonl`) |
| "Children collaborate without parent relay" | DL-6 (reject A), DL-7 (topic channels) | `04-verification/communication-structures/{INVESTIGATION,PLAN,FINDINGS,RESULTS}.md`, `context-injection-design.md` |
| "Extensible / replaceable components" | DL-8 (interface economy), DL-9 (policy extraction) | `03-implementation/plugin/investigation/README.md`, `00-intent/platform-evaluation/README.md` |
| "Recover from failure without grinding" | DL-10 (self-healing) | `02-architecture/concepts/self-healing/README.md`, `00-intent/competitive-differentiation/README.md`, `04-verification/gap-analysis/README.md` G2 RESOLVED |
| "Choose collaboration topology on evidence" | DL-11 (benchmark-driven verification) | `04-verification/communication-structures/{RESULTS.md, metrics-cells.json, FINDINGS.md}` |
| "Composable CLI for automation" | DL-12 (CLI-first minimal) | `01-product/requirements/README.md` FR/NFR, `06-evolution/backlog.md` |
| "Delegate when it pays; right-size ceremony" | DL-13 (golden delegation rule) | `02-architecture/methodology/README.md`, `skills/delegation-guidelines/SKILL.md`, `skills/tool-motivations/SKILL.md` |
| "Child autonomy safe via intent" | DL-15 (mission-command briefs) | `skills/mission-command/SKILL.md`, `02-architecture/concepts/delegation-model/README.md`, `03-implementation/` policies (BriefPolicy) |
| "Definition state stays navigable and canonical, not accumulated" | DL-17 (node model) | `02-architecture/decisions/AD-009.md`, `product-breakdown/README.md` (Node Model), `product-breakdown/tools/check_node_size.py`, `docs/references/information_hygiene.md` |

## What Is Not Yet Traced (open work)

- **REQ-1..15** (collaboration spec, `02-architecture/multi-agent-coordination/collaboration-setting/README.md`) — to be linked to ADR records and the team-charter/channel machinery once the comms implementation lands (see `06-evolution/roadmap.md`).
- **G1–G13** (`04-verification/gap-analysis/README.md`) — each gap to be linked to the decision that caused it and the IMP that fixes it.
- **VISION pillars / success criteria** (`00-intent/VISION.md`) — each pillar/criterion to be traced to its realizing artifact.

These seed rows are the highest-value links from the review; completing the map is an ongoing maintenance duty, not a one-time artifact.