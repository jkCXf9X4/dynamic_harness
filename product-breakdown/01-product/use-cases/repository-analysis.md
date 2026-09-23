---
title: "Use-Case — Repository Analysis"
category: use-case
summary: >
  Inventory, audit, and understand an existing codebase: security review, code
  quality, TODO/debt inventory, structure mapping. The canonical read-heavy
  family — discovery, parallel delegation, progressive disclosure, read-only.
related:
  - ../../02-architecture/concepts/delegation-model/README.md
  - ../../02-architecture/concepts/artifact-system/README.md
  - ../../00-intent/VISION.md
---

# Repository Analysis

Analysis over a codebase whose shape is not yet fully known. The root agent must
**discover** first, then **parallelize** by concern, then **synthesize**
already-verified findings.

## Scenario (root task)

> "Audit `src/` for security vulnerabilities and write a prioritised findings
> report to `reports/security.md`, each finding with file:line and a suggested
> fix class. Do not modify any source."

## Why it fits

- **Discovery** work: `glob` to enumerate, `grep` to find by symbol/behavior,
  `read` to confirm.
- Splits cleanly into **parallel units by concern** (security, performance,
  style, TODO debt) — a textbook delegation tree.
- Output is a **durable, versioned artifact**; commits give an audit trail, and
  **read-only by design** fits sandbox confinement and "flag issues, don't fix".

## Decomposition

A root **orchestrator** splits by concern instead of reading every file:

| Sub-agent | Role / scope | Output artifact |
|---|---|---|
| Security Auditor | Flag vulnerabilities, don't fix; `bandit`/`grep` risky calls, HIGH only | `reports/security_findings.json` |
| Code Reviewer | Correctness + readability; `read` key modules + tests | `reports/code_review.md` |
| TODO/Debt Scout | TODO/FIXME/`XXX` inventory via `grep` | `reports/todos.txt` |
| Structure Mapper | Module graph / public surface via `glob` + import grep | `reports/structure.json` |

All four delegated **in the same turn** (parallelism). The root then VERIFYs.

## Tool flow & constraints

- **Discover before read**: `glob("**/*.py")`, then `grep`; only `read` files
  that surface as relevant. Reviewers never `edit`/`bash`; `bash` has no shell
  operators — `bandit` runs as a plain command and its JSON is `read`, not piped.
- Each sub-agent **writes one disk artifact** and `report()`s a compact summary
  + artifact ID (progressive disclosure), never a raw dump upward.

## Verification & acceptance

The parent must **not synthesize from assumed results**: `read_artifact` each
child's summary, confirm its file exists and covers the accept criteria (`HIGH`
findings with file:line), and `converse`/re-delegate a missing or empty one —
never report the slot complete. Then `report()` with every verified `artifact_ids`.

Self-healing: a prose-only answer → Layer 1 (resume once with a "write the file
now" nudge); churning `grep`s → Layer 3 (fresh worker, pointed at what the dead
one wrote); a non-converging crawl → split smaller roles and escalate (Layer 4)
(`../../02-architecture/concepts/self-healing/README.md`).

## Fit checklist & caveats

- **Fits well**: unknown-shape workspace, parallel concerns, durable report.
- **Strain**: a huge artifact — prefer `read` token paging over one giant read.
- **Watch**: read-only roles must not "help" by editing; enforce a precise `role`.
- **Not a fit**: "explain the codebase in chat" — no material artifact.
