---
title: "Use-Case — Change & Validation"
category: use-case
summary: >
  Work that modifies a codebase and must be proven correct: bug fixes with
  verification, test-authoring for coverage, cross-cutting refactors, and small
  self-contained code generation.
related:
  - ../../02-architecture/concepts/delegation-model/README.md
  - ../../02-architecture/concepts/agent-lifecycle/README.md
  - ../../02-architecture/concepts/self-healing/README.md
---

# Change & Validation

Making a change and proving it. The shape is always small, well-scoped edits and
then the relevant tests — often **leaf-to-small-orchestration**, not deep trees.

## Scenario A — Bug fix, root-cause

> "Login returns a 500 when the password contains `#` or `@`. Find the root cause
> in `src/auth/password.py`, apply a minimal fix, run `pytest tests/test_auth.py`,
> and report to `reports/fix_report.md`. Do not change the database schema or the
> frontend."

**Why it fits:** bounded and *verify-first*; the acceptance criterion ("tests
pass") is built into the task, so `report()` claims a real, checked result.

**Flow:** `read` the module(s) + tests → `edit` (surgical) or `write` (whole-file)
the fix → `bash pytest tests/test_auth.py` → `report` with the fix, `pytest`
result, and `files_written`. Red → re-read, adjust, re-run (Layer 0); repeated
identical write → detection (Layer 3).

## Scenario B — Test-coverage authoring (benchmark `codegen` shape)

> "Write coverage for the three most-untested public functions in
> `core/runtime.py` — `delegate`, `deliver_report`, `reset`. Add tests to
> `tests/test_runtime.py` matching existing fixtures/assert style, run
> `pytest --cov=...`, and write a summary to `reports/coverage.md`. Do not modify
> implementation code."

**Why it fits:** verifiable output (passing tests), a hard scope boundary on
implementation code, and a repeatable pattern — the benchmark's `codegen` ground
truth is *the tests actually passing*. **Flow:** `read` the functions → `read` an
existing test file for conventions → `write`/`edit` new tests → `bash pytest` →
`report` with the coverage number.

## Scenario C — Cross-cutting refactor (orchestrator)

> "Rename the error-handling module across `src/` and its callers and verify no
> regressions."

One mechanical transformation across many files — ideal for **parallel,
role-scoped sub-agents**, one per area, each running bounded `edit`s then that
area's tests. `bash` has **no shell operators**, so each renamer drives the editor
tools; broad refactors split further (AP-4). Root VERIFYs diff + test, then reports.

## Verification & acceptance

Prefer genuine verification (test run / recompile) over the agent's own
assertion; `bash pytest` (or the target build) is ground truth. A parent seeing a
completed auto-edit agent must still `read` its diff and re-run the affected test
column (*"never trust the return summary — verify artifact"*), reporting only the
verified fix, command, and result.

## Fit checklist & caveats

- **Fits well**: per-area changes with a clear `pytest`/build oracle, coverage
  tests, small codegen with assertions.
- **Strain / watch**: a refactor across dozens of files must be broken into
  per-area sub-agents, each self-contained and testable; `bash` cannot do
  shell-wizardry (no pipes/redirects/`&&`), so "run all tests" is one `pytest`
  command, not a compound.
- **Not a fit**: a change with no accept criteria and no verify-before-reporting
  gate — drifts into blind synthesis (anti-patterns AP-3/7).
