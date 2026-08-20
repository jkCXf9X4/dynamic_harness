---
title: "Use-Case — Change & Validation"
category: use-case
summary: >
  Work that *modifies* a codebase and must be proven correct: bug fixes with
  verification, test-authoring for coverage, cross-cutting refactors, and small
  self-contained code generation. Relies on edit/write + bash-driven
  verification and the analyze → implement → verify loop.
related:
  - concepts/delegation-model.md
  - concepts/agent-lifecycle.md
  - concepts/self-healing.md
---

# Change & Validation

This family is about **making a change and proving it**. The shape is always the
same — small, well-scoped edits, then run the relevant tests — so these are
often **leaf-to-small-orchestration** use-cases rather than deep trees.

## Scenario A — Bug fix, root-cause

> "Login returns a 500 when the password contains `#` or `@`. Find the root
> cause in `src/auth/password.py`, apply a minimal fix, run
> `pytest tests/test_auth.py`, and report to `reports/fix_report.md`. Do not
> change the database schema or the frontend."

**Why it fits:** a bounded, *verify-first* task. The agent uses `read` to
investigate, `edit`/`write` for the fix, then `bash pytest` to prove it. The
acceptance criterion ("tests pass") is built into the task and the verification
is deterministic, so `report()` claims a real, checked result.

**Flow:**
1. `read` the suspected module(s) + tests to form a hypothesis.
2. `edit` (first-occurrence, surgical) or `write` (whole-file) the minimal fix.
3. `bash pytest tests/test_auth.py` to confirm green.
4. `report` with `summary` stating the fix + `pytest` result, plus
   `files_written`.

**Failure/self-healing:** test still red → re-read the failing section, adjust,
    re-run (in-loop Layer 0). Repeated identical write → detection (Layer 3) if
    the context is truly stuck; otherwise just a bounded retry.

## Scenario B — Test-coverage authoring (the benchmark `codegen` shape)

> "Write coverage for the three most-untested public functions in
> `core/runtime.py` — `delegate`, `deliver_report`, and `reset`. Add tests to
> `tests/test_runtime.py` matching the existing fixtures/assert style, run
> `pytest --cov=...`, and write a summary to `reports/coverage.md`. Do not
> modify implementation code."

**Why it fits:** verifiable output (tests that pass), a hard scope boundary on
implementation code, and a repeatable pattern. Mirrors the benchmark's
`codegen` task where ground truth is the *tests actually passing*.

**Flow:** `read` the functions → `read` an existing test file for conventions →
`write`/`edit` new tests → `bash pytest` to confirm → `report` with the
coverage number it measured.

## Scenario B — Cross-cutting refactor (orchestrator)

> "Rename the error-handling module across `src/` and its callers and verify no
> regressions."

**Why it fits:** one mechanical transformation spread over many files — ideal
for **parallel, role-scoped sub-agents**, one per area, each doing a bounded
set of `edit`s and then running that area's tests.

**Root decomposition:**

```
Rename in src/core/     → role "Mechanical Renamer", project-level patterns
Rename in src/cli/      → (parallel, own test run)
Rename in tests/        → (parallel, update assertions)
          ↓ VERIFY each by reading its diff artifact + running the local test
Root: synthesize a combined `reports/refactor.md` + change log; report with all ids
```

Constraints: `bash` has **no shell operators** so each renamer drives the editor
tools (`edit` per first-occurrence / `write`), not a bulk regex replace in one
call; a broad, cross-tree refactor must be split further rather than
mega-delegated (guides AP-4).

## Verification & acceptance

- Prefer genuine verification (a test run / recompile) over the agent's own
  assertion. `bash pytest` (or the target build) is the ground truth, matching
  the benchmark's **failable verifier** idea.
- The parent that *sees* a **completed** auto-edit agent must still `read` its
  artifact/diff and ideally re-run the affected test column, under the
  delegation rule *"never trust the return summary — verify artifact"*.
- Report only verified truth: state the fix, the test command, and its result.

## Fit checklist & caveats

- **Fits well**: single-file or per-area changes with a clear `pytest`/build
  oracle, coverage tests, small codegen with assertions.
- **Strain**: a refactor across dozens of files can become a mega-delegation; it
  must be broken into per-area sub-agents, each self-contained and testable.
- **Watch**: `bash` cannot do shell-wizardry (no pipes/redirects/`&&`); a
  "run all tests" orchestration is expressed as one `pytest` command, not a
  compound.
- **Not a fit**: a change with no stated accept criteria and no "verify before
  reporting" gate — that drifts into blind synthesis (see anti-patterns AP-3/7).