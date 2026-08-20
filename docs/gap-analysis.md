---
title: "Gap Analysis — Concepts & Use-Cases vs Implementation"
category: meta
summary: >
  Evaluation of what the concepts (VISION, delegation model, artifact system,
  self-healing) and the deduced use-cases promise versus what the runtime and
  tools actually deliver. Identifies the missing machinery, dead code, and
  doc/example drift that would block a use-case from working as described.
related:
  - concepts/artifact-system.md
  - concepts/self-healing.md
  - concepts/delegation-model.md
  - use-cases/index.md
  - ../VISION.md
---

# Gap Analysis

An honest audit of the framework. "Missing" here means one of three things:

- **Mechanism promised by a concept but not implemented** (prompt discipline is
  not a mechanism),
- **Code that exists but is unreachable or inert** (dead plumbing), or
- **Documented behavior that the code contradicts** (drift that would trip up an
  agent following the docs).

Each gap cites the evidence and the use-case it breaks. Gaps are labeled
**P0** (breaks a core promise), **P1** (blocks a documented capability or a
real-world run), **P2** (quality-of-life / accuracy).

## What Is Actually Solid

Before the gaps — the parts that demonstrably back the use-cases:

| Capability | Evidence | Serves use-cases |
|---|---|---|
| Parallel decomposition (batch delegates, gathered) | `agent.py:553-600, 709-742` | all families |
| Role-scoped tool allow-list enforced in code (orchestrator can't do hands-on work) | `tools/registry.py:27-44, 66-79` | repository-analysis, change |
| Prune/restore/compress context management | `context.py:126-275` + `manyfiles` benchmark | pipelines-and-jobs |
| Checkpoint persistence + `Runtime.resume` + CLI `/resume` | `checkpoint.py`, `runtime.py:190-243`, `terminal.py:436-443` | pipelines-and-jobs |
| Self-heal at the root boundary (resume-once / fresh worker) | `runtime.py:334-382` | all |
| Sandbox + SSRF guard + gitignore filter + path/repo locks | `tools/filesystem.py:96-105`, `network.py:30-59`, `runtime.py:99-140` | change, embedding |
| Token usage, JSONL traces, commits, `index.jsonl` provenance | `usage.py`, `trace.py`, `memory/repository.py`, `runtime.py:562-641` | evaluation-and-qa |
| Deterministic, failable benchmark verifiers + prompt optimizer | `benchmark/tasks.py`, `scripts/run_optimize.py` | evaluation-and-qa |
| 19 tools registered and extensible | `tools/registration.py` | embedding |

---

## P0 — Breaks a core concept promise

### G1. VERIFY is prompt discipline, not a mechanism; acceptance criteria are never checked

**Concept promise:** the mandatory `ANALYZE → DECOMPOSE → DELEGATE → VERIFY →
SYNTHESIZE` loop (VISION), success criterion #1 "every sub-agent's output
verified (artifact read, content confirmed)", and `plan`'s *acceptance criteria*
are meant to gate termination.

**Implementation:** the only mechanical check is `_has_deliverable`
(`runtime.py:261-273`) — file *existence*, not content or correctness. The
`plan` tool records `acceptance` into the `FocusLedger`
(`tools/planning.py:25-35`, `agent.py:220-242`), but **nothing ever evaluates
them**. Blind synthesis (anti-patterns AP-3/AP-7) is undetectable by the
runtime; "done" is whatever the agent's `report()` declares.

**Breaks:** every use-case that relies on "verify before synthesize" as a
guarantee — most directly `repository-analysis.md` §Verification, and the
whole evaluation-and-qa family (which currently works only because the
*benchmark* adds its own verifier).

**Fix direction:** a report-time acceptance check — e.g. the parent's
`read_artifact` + a mechanical "does the artifact mention the acceptance
terms / does it exist and is non-empty" gate on children that declared
`plan(acceptance=...)`, plus a runtime flag `verify_children=true` that
re-delegates or escalates a child whose acceptance criteria are unmet.

### G2. Delegation-boundary heal misses prose-completed children

**Concept promise:** self-healing Layer 1 "resume-once" is for *"terminated
without a normal report, or terminated with a report but produced no
deliverable"* — the prose-answer failure mode is the motivating example
(`self-healing.md:86-88`).

**Implementation:** at the **root** boundary `_recover` checks the deliverable
(`runtime.py:347`). At the **delegate** boundary, `_recover` is only invoked
when `child.last_failure is not None` (`agent.py:735-737`, `agent.py:827-829`).
A child that completes in prose (status `completed`, no artifact, no
`files_written`) is **not** healed there — the parent receives a "completed"
result with nothing to verify, exactly the failure the concept says should be
caught.

**Breaks:** any delegation where a child answers in prose; e.g. the optimizer
generation-agent flake that motivated the design, `documentation-and-knowledge`
(an agent writes prose instead of the doc file).

**Fix direction:** at the delegate boundary, run `_recover` on any child whose
outcome is a report without a deliverable (`last_failure is None` AND
`not _has_deliverable(child)`), matching the root check.

### G3. Progressive disclosure is data, not an interface; `raw_data` is dead

**Concept promise:** a six-level disclosure ladder — headline → 200-char →
1000-char → technical → full → raw, with parents "reading summaries first and
progressively load[ing] more detail as needed" (`artifact-system.md:22-61`).

**Implementation:** `read_artifact` returns **every non-empty view in one
response** (`tools/agents.py:224-230`). There is no way to ask for "just the
headline" or "just the 1000-char summary", so the lazy-load economics (300-token
preview vs 30K dump) are not achievable *in the tool loop* — a parent that calls
`read_artifact` on a big child gets the full report whether it wants it or not.

Separately, `ArtifactView.raw_data` is **never written anywhere**
(`runtime.py:429-435` fills only headline/summary_200/summary_1000/technical/
full_report); the `raw_data` view is read but always empty — the ladder
effectively has five steps.

**Breaks:** the cost story of `repository-analysis` and `research-and-synthesis`
(parents consuming summaries cheaply), and `documentation-and-knowledge`
Scenario C's `hierarchical_summary`.

**Fix direction:** add a `level` parameter to `read_artifact`
(`headline|summary|technical|full|raw`), populate `raw_data` from a child's
`files_written` payload or the sidecar, and make the default level `summary`.

### G4. `artifact_ids` are free-form strings; agent-written files are not linked to the artifact

**Concept promise:** artifacts are "the primary communication mechanism" — a
parent resolves a child's output via its artifact ID (`artifact-system.md:16`,
`delegation-model.md:126-141`).

**Implementation:** there are **two disjoint stores**:
- report *metadata* (the `Artifact`) lives in `artifact_root/<uuid>/` and is
  indexed by artifact **UUID**,
- the agent's *actual findings files* live in `generated_root` (the sandbox).

`read_artifact(id)` resolves a UUID, or falls back to resolving an **agent id**
(`tools/agents.py:206-223`) — a raw **file path** (which the docs and examples
use as `artifact_ids`, e.g. `/tmp/findings.json`) will not resolve. Worse, the
run `index.jsonl` maps each artifact to the *metadata* directory
(`runtime.py:586`), and `files_written.json` is stored but **never surfaced**
through `read_artifact` or `provenance`. So "the artifact is the truth" is only
true for the 300-token summary — the substantive file is reachable only by the
parent guessing a path and using `read`.

**Breaks:** every artifact-driven use-case at the "parent reads the child's
actual output" step (`repository-analysis` §Verification, `change-and-validation`
§Verification), and the evaluation/provenance story.

**Fix direction:** write agent `write()` output under the *artifact* directory
(or copy/link it at `deliver_report` time using `payload.files_written`), and
make `read_artifact`/`provenance`/`index.jsonl` surface those files.

---

## P1 — Blocks a documented capability or real-world run

### G5. Sandbox rejects the documented `/tmp/...` write patterns

**Concept/docs:** `delegation_descriptions.md`, `task_framing.md`,
`artifact-system.md` all instruct agents to "write to `/tmp/security_findings.json`
and report with the artifact path".

**Implementation:** `write`/`edit` resolve absolute paths and reject anything
outside `generated_root`/CWD with `"Path ... is outside the workspace"`
(`tools/filesystem.py:96-105`). Under the default CLI the sandbox **is the
user's CWD** (`cli/common.py` never sets `generated_root`), so `/tmp/...` always
fails — and conversely the agent can freely overwrite the user's own project
files. Two distinct problems: doc drift (examples fail as written) and a weak
default sandbox (no output isolation).

**Breaks:** anyone copy-pasting the examples; the safety story in the use-cases.

**Fix direction:** make the examples use workspace-relative paths + artifact
IDs; consider a default `generated_root` (e.g. `.dynamic-harness/out/`) for CLI
runs so agents don't write into the source tree by default.

### G6. Custom agent classes cannot be spawned by the LLM

**Concept/docs:** VISION pillar 7 "parent-defined specialized agents" and
`guides/custom-agents.md:40-42` ("Via the delegate() tool in the LLM loop:
`delegate(description=..., agent_type=...)`").

**Implementation:** the `delegate` tool schema (`tools/agents.py:25-31`) and
`run_delegate_tool` (`agent.py:797-829`) accept only
`description`/`role`/`system_prompt`. `agent_type` is honored only by the
programmatic `Runtime.delegate`/`Runtime.run` (`runtime.py:160, 390-411`). A
parent inside a live tree cannot choose a registered specialist class for its
child — the whole specialization story is reachable only from host code.

**Breaks:** `embedding-and-integration.md` Scenario B ("the LLM can spawn it via
`delegate(..., agent_type=...)`"), and the VISION pillar.

**Fix direction:** add `agent_type` to the `delegate` tool schema + allow-list
registered names, or document that custom classes are a programmatic-only
feature.

### G7. Self-heal Layer 2 is not a distinct mechanism

**Concept:** `self-healing.md:56-58` describes Layer 2 — "parent `converse()` /
resumes the child with the failure reason" — as a separate policy tier from
Layer 1.

**Implementation:** the parent boundary reuses the same `_recover`
(`agent.py:735-737`) as the root boundary; there is no parent-side diagnosis and
no separate converse-based heal. Combined with G2, the *failure* case is handled
but the *prose-completion* case (which Layer 1 is explicitly about) is not.

**Breaks:** the layered policy as documented; makes "Layer 1 → miss → Layer 3"
untestable at the delegation boundary.

**Fix direction:** either document that Layer 2 = Layer 1 applied at the parent
boundary, or implement a distinct parent-side diagnosis + `converse` heal path,
and fix the G2 deliverable check.

### G8. Budgeting / cost-control is dead plumbing

**Concept:** VISION is built on "minimize cost"; the `ask`/`escalate` model
implies an agent can request more budget (`BudgetRequest`).

**Implementation:** `request_more_budget` (`agent.py:835-842`),
`deliver_budget_request` (`runtime.py:473-474`) and the `on_budget_request`
handler all exist, but **no tool exposes them to the loop** and there is no
spend cap or enforcement anywhere. An agent cannot request a budget increase,
and a run cannot be stopped at a token ceiling.

**Breaks:** any cost-sensitive production use (the stated #1 motivation of the
project); `embedding-and-integration` (a consumer cannot set a budget).

**Fix direction:** a `request_budget` tool wired to an interactive handler +
configurable hard cap that force-fails or escalates past it.

---

## P2 — Quality-of-life / accuracy

### G9. Runtime reports tokens only; cost exists only in the benchmark

`config.llm.price_*` feed the benchmark (`benchmark/run.py:88-89`); the Runtime
`total_usage()` returns tokens (`usage.py:51-63`) and the CLI prints tokens. The
"cost" half of the cost/quality story is not available to a library consumer or
the CLI.

### G10. `usage.message_count` is overwritten, not cumulative

`usage.py:36` sets `message_count` to the latest send size rather than
accumulating, so `get_usage()["message_count"]` is the last message count, not
the total processed. Misleading for cost analysis.

### G11. Docs drift on tool count and extension surface

- `api/runtime.md:44` says "17 default tools"; `AGENTS.md` and
  `tools/registration.py` register **19**.
- `guides/prompt-optimization.md:149-152` says the prompt loads "at agent.py:26";
  it now loads in `core/prompts.py:13` (cosmetic).
- `LLMConfig.temperature`/`max_tokens` are never set from config — always
  defaults (`agent.py:335`, `config.py`).

### G12. No agent-facing provenance / trace tool

Failure triage (use-cases `evaluation-and-qa.md` Scenario C) requires reading
`trace.jsonl` via `read`, and `/provenance`/`/trace` are CLI-only commands.
There is no `provenance`/`trace` tool, so a QA agent inside a run can't self-audit
its own branch.

### G13. Heal budgets are per-process

`_heal_counts` is in-memory (`runtime.py:86, 350`); a `Runtime.resume` after a
process restart restarts heal budgets at zero, so bounded-retry guarantees do not
survive a restart (only the checkpoint/rot detection per run does).

---

## Summary

| # | Gap | Severity | Fixing enables |
|---|---|---|---|
| G1 | No mechanical verification; acceptance criteria unused | **P0** | trustable orchestration |
| G2 | Delegate-boundary heal misses prose completions | **P0** | self-heal as documented |
| G3 | Disclosure not progressive; `raw_data` dead | **P0** | cheap parent reads |
| G4 | `artifact_ids` / files not linked to artifact | **P0** | "artifact is the truth" |
| G5 | Sandbox vs `/tmp` examples; weak default isolation | P1 | examples + safety |
| G6 | LLM cannot spawn custom agent classes | P1 | VISION pillar 7 |
| G7 | Layer 2 heal is not distinct (and G2) | P1 | layered policy |
| G8 | Budget plumbing is inert | P1 | cost control |
| G9–G13 | Cost, counters, docs drift, agent-side provenance, durable heal budgets | P2 | polish |

Recommended first pass: **G2, G4, G3** (small, high-leverage, make the
delegation/verification story real), then **G8** and **G5** before advertising
cost-control and example-driven onboarding.