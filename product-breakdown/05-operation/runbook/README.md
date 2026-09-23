# Runbook — dynamic_harness (Index)

How authors install, test, benchmark, and release. All commands run from the
**repo root** unless noted; Python 3.10+ required. Created 2026-09-21 (fills
review GAP-5 — previously no runbook existed; onboarding had to
reverse-engineer this).

## Contents

- [setup-and-test.md](setup-and-test.md) — environment/config, install, tests, node-size check, lint/format.
- [benchmarks.md](benchmarks.md) — prompt benchmark CLI, comms benchmark, scaling diagnostics.
- [build-and-release.md](build-and-release.md) — build, version, release practice.

Release decisions (bumping, breaking changes) are operation decisions recorded as
`OD`-prefixed ADRs per the product-breakdown convention.
