---
title: "Use-Cases — Index"
category: use-case
summary: >
  A deduced taxonomy of plausible use-cases for Dynamic Harness, grounded in the
  concepts (delegation model, artifact system, lifecycle, self-healing) and the
  actual tools and runtime. Each family links to the capabilities it relies on and
  the fit criteria that decide whether a task belongs here at all.
related:
  - concepts/delegation-model.md
  - concepts/artifact-system.md
  - concepts/agent-lifecycle.md
  - concepts/self-healing.md
  - ../VISION.md
  - ../guides/programmatic-usage.md
---

# Use-Cases

This directory deduces **plausible use-cases** for Dynamic Harness from the
concepts (`docs/concepts/`) and the concrete runtime/tools in `src/`. Use-cases
are the "why" that sits between a user's real-world goal and the framework's
mechanics — they answer *"what would someone actually use this for?"*.

## Fitness Filter

Not everything is a good Dynamic Harness use-case. The framework is
**not** a chatbot, not a shared-memory assistant, and not a code-generation
platform. A good use-case has most of these properties:

| Signal | Fits | Misses |
|---|---|---|
| Work decomposes into parallel units | ✓ orchestrate sub-agents | Single-turn Q&A |
| Task needs 2+ tool calls | ✓ delegate | One `read` on a known path |
| Output is a durable, verifiable artifact | ✓ write to disk + report | In-memory reply ("chat") |
| Search/analysis over an unknown workspace | ✓ glob/grep/read discovery | Path already known exactly |
| Long or costly — worth resuming/checkpointing | ✓ checkpoint + `/resume` | Trivial and idempotent |
| Every result benefits from an audit trail | ✓ commits + trace store | Ephemeral, throwaway |

Conversely, negative examples: *"explain my codebase conversationally"* (a
chatbot job, not a material artifact), *"just tell me the answer"* (no tool
loop needed), *"run one shell command"* (a leaf, not an orchestration).

## Use-Case Families

| Family | What class of work | Archetype tool flow | Primary doc |
|---|---|---|---|
| **Repository analysis** | Inventory, audit, security, TODO/debt, structure | `glob`/`grep`/`read` → parallel role-scoped delegates → synthesize | [repository-analysis.md](repository-analysis.md) |
| **Change & validation** | Bug fix, tests, refactor, small codegen | `read`/`edit`/`write` → `bash` to verify → report | [change-and-validation.md](change-and-validation.md) |
| **Documentation & knowledge** | Generate docs, doc API surface, curate a reference library | `glob`/`read` → summarize → `write` artifact | [documentation-and-knowledge.md](documentation-and-knowledge.md) |
| **Research & synthesis** | External research, comparison, source-aggregation | `webfetch` (parallel delegates) → synthesize artifact | [research-and-synthesis.md](research-and-synthesis.md) |
| **Pipelines & jobs** | Batch extraction/transformation, long resumable jobs | `bash`/`write` per item → `prune`/`restore` → checkpoint/resume | [pipelines-and-jobs.md](pipelines-and-jobs.md) |
| **Evaluation & QA** | Benchmark suite, prompt A/B, failure triage | deterministic verifiers, fresh-Runtime runs | [evaluation-and-qa.md](evaluation-and-qa.md) |
| **Embedding & integration** | Library use, custom agents/tools, product-specific workflows | `Harness`/`Runtime` API + custom registry | [embedding-and-integration.md](embedding-and-integration.md) |

## How a Use-Case Maps to the Architecture

Every use-case below is built from the same load-bearing concepts:

1. **Decomposition** — the goal is split into independent, role-scoped
   sub-agents (`delegate` in one turn for parallelism). Parents orchestrate.
2. **Artifacts, not memory** — each sub-agent writes findings to disk and
   returns a compact summary + artifact ID (**progressive disclosure**). Parents
   read summaries first, load detail only on `read_artifact`.
3. **Verify before synthesize** — never report a child's output as if you had
   read it; confirm the artifact on disk first (guides/delegation-model §VERIFY).
4. **Self-healing** — a blunt failure resumes; a poisoned context spawns a fresh
   worker; a structural failure escalates (`docs/concepts/self-healing.md`).
5. **Provenance** — each completed task writes an immutable artifact + a Commit;
   every run is reproducible and auditable from the trace (`index.jsonl`).

## Tool Vocabulary Referenced Below

Typical tool choices per step (see `docs/references/tool_motivations.md` for the
full rationale):

- Discover: `glob` (enumerate), `grep` (search contents by symbol/behavior)
- Read: `read` (read summaries first; page large files instead of one giant read)
- Change: `edit` (targeted first-occurrence), `write` (whole/new content)
- Act/verify: `bash` — but **no shell operators** (no `|`, `>`, `&&`); no sandbox escape (paths confined to `generated_root`/CWD)
- External: `webfetch` — restricted to public/non-private hosts, 200 KB cap
- Coordinate: `delegate`, `converse` (nudge an existing child), `read_artifact`, `ask`
- Context: `compress`, `prune`, `restore`
- Terminate: `report` (success), `escalate` (blocked), `fail` (unrecoverable)

## Reading the Family Docs

Each family doc follows the same shape:

1. **Scenario** — a concrete operator goal phrased as a root task.
2. **Why it fits** — which pillars/capabilities are exercised.
3. **Decomposition** — the roles/delegations the root agent should spawn.
4. **Tool flow** — what each sub-agent reaches for (and constraints).
5. **Verification & acceptance** — how "done" is confirmed.
6. **Failure mode** — how self-healing applies.
7. **Fit checklist & caveats** — when the use-case strains the design and what to watch for.