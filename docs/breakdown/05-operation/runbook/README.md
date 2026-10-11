---
title: Runbook — dynamic_harness (Index)
summary: How authors install, test, benchmark, and release. All commands run from the repo root unless noted; Python 3.10+ required.
---

# Runbook — dynamic_harness (Index)

How authors install, test, benchmark, and release. All commands run from the
**repo root** unless noted; Python 3.10+ required.

Release decisions (bumping, breaking changes) are operation decisions recorded as
`OD`-prefixed ADRs per the product-breakdown convention.

## Excludes
- Decision records: the decision archive (`docs/archive/archive.zip`, `OD-*`).

## Contents

<!-- pb:index:start -->
<!-- GENERATED FILE — do not edit. Regenerate with pb-registers. -->
- **INFO-136** [Benchmark Runners](benchmarks.md) — Run the prompt, comms, and scaling benchmarks — commands, inputs, and output locations.
- **INFO-137** [Build & Release](build-and-release.md) — Build the wheel and run the release practice — verify, benchmark gate, version, build, document, regenerate, ship.
- **INFO-138** [Setup & Test](setup-and-test.md) — Install, configure, and test the runtime — API key, layered config, pytest, node-size check, pre-commit.
<!-- pb:index:end -->
