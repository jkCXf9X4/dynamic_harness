---
title: "Use-Case — Repository Analysis"
category: use-case
summary: >
  Inventory, audit, and understand an existing codebase: security review, code
  quality, TODO/debt inventory, structure mapping, dependency analysis. The
  canonical read-heavy family — it exercises discovery tools, role-scoped
  parallel delegation, progressive-disclosure verification, and read-only
  discipline.
related:
  - concepts/delegation-model.md
  - concepts/artifact-system.md
  - ../VISION.md
---

# Repository Analysis

Analysis over a codebase whose shape is not yet fully known. The root agent may
not know which files matter; it must **discover** first, then **parallelize**
the investigation by concern, then **synthesize** already-verified findings.

## Scenario (root task)

> "Audit `src/` for security vulnerabilities and write a prioritised findings
> report to `reports/security.md`, each finding with file:line and a suggested
> fix class. Do not modify any source."

## Why it fits

- Investigation is canonical **discovery** work: `glob` to enumerate, `grep` to
  find by symbol/behavior, `read` to confirm. Exactly what the discovery tools
  exist for.
- It splits cleanly into **parallel units by concern** (security, performance,
  style, TODO debt) — a textbook delegation tree.
- Output is a **durable, versioned artifact** (`reports/security.md`), so
  artifact-driven communication + commits give an audit trail.
- **Read-only by design** fits the sandbox model (workspace confinement) and the
  "flag issues, do not fix them" role discipline.

## Decomposition

A root **orchestrator** should not read every file itself. It splits by concern:

| Sub-agent | Role | Scope | Output artifact |
|---|---|---|---|
| Security Auditor | Flag vulnerabilities, do not fix | `bandit`/`grep` for risky calls, HIGH-severity only | `reports/security_findings.json` |
| Code Reviewer | Correctness + readability, genuine issues only | `read` key modules + their tests | `reports/code_review.md` |
| TODO/Debt Scout | TODO/FIXME/`XXX` inventory | `grep` across tracked extensions | `reports/todos.txt` |
| Structure Mapper | Module graph / public surface | `glob` + import grep | `reports/structure.json` |

All four delegated **in the same turn** (parallelism). The root then VERIFYs.

## Tool flow & constraints

- **Discover before read**: `glob("**/*.py")` to list; `grep` to locate the
  security/code review targets; only `read` files that surface as relevant.
- **Read-only restriction** is enforced by the sandbox and by role; reviewers do
  not `edit`/`bash` (no changes). `bash` is a raw executor **with no shell
  operators** — a security tool like `bandit` runs as a plain command, and its
  JSON output is read as an artifact (`read`) not piped.
- Each sub-agent **writes one disk artifact** and `report()`s a compact summary
  + artifact ID (progressive disclosure), never a raw megabyte dump upward.

## Verification & acceptance

Per the delegation model, the parent must **not synthesize from assumed
results**:

1. After the delegates return, `read_artifact` each child's summary.
2. Confirm the artifact file exists and is non-empty — `read`
   `reports/security.md` far enough to confirm it covers the accept criteria
   (`HIGH` findings with file:line).
3. Missing/empty child → `converse(child, "the artifact is empty — write the
   findings file")` or re-delegate; never report their slot as complete.
4. Then `report()` with `artifact_ids` for every verified child artifact.

## Failure mode (self-healing)

- A child answers in prose without writing the artifact → **Layer 1**: resume it
  once with a "write the file now" nudge (`docs/concepts/self-healing.md`).
- A child hits repeated identical calls (churning `grep`s with no result) →
  **Layer 3** fresh worker, reason injected, pointed at whatever the dead worker
  already wrote.
- The whole investigation turns into a crawl (>500 turns, no convergence) →
  the root decomposition was too broad; re-delegate smaller role slots and
  **escalate** the rest (`Layer 4`).

## Fit checklist & caveats

- **Fits well**: unknown-shape workspace, parallel concerns, durable report.
- **Strain**: if the artifact is huge, prefer `read` with token paging and
  multiple progressive passes rather than one giant artifact.
- **Watch**: read-only roles must not "help" by editing; enforce with a precise
  `role` that forbids implementation.
- **Not a fit**: "explain the codebase to me in chat" — no material artifact is
  demanded; this is a chatbot job (see VISION "What this is not").