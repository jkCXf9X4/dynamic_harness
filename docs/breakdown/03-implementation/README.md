---
title: Layer 03 — Implementation
summary: With what concrete assets is it realized?
---

# Layer 03 — Implementation

**With what concrete assets is it realized?**

This layer records the concrete, code-level facts of the runtime: files, scripts, interfaces, configs.

- The runtime is Python 3.10+ under `src/dynamic_harness/`; the assets stay at the repo root.
- Leaves hold the facts; this index only orients a reader top-down.

## Owns
- Repo layout and build assets: `INFO-201`
- CLI surface (entry point, flags, REPL commands): `INFO-197`
- Runtime config schema (keys, defaults, env vars, layering): `INFO-198`
- Tool registry inventory (34 tools): `INFO-199`
- Extension points (agent classes, reactive policies, tools, skills): `INFO-200`

## Excludes
- Scope, capabilities: `01-product/`
- Architecture rationale, organizing design: `02-architecture/`
- Proof criteria, test mechanics: `04-verification/`
- Release policy: `05-operation/`
- Run and test procedures: `INFO-138`
- Future features: `06-evolution/`
- Plugin-readiness investigation (open, no ID yet): `06-evolution/investigations/plugin/`
- Decisions: the decision archive (`docs/archive/archive.zip`, read via `pb archive`)

## Contents

<!-- pb:index:start -->
<!-- GENERATED FILE — do not edit. Regenerate with pb-registers. -->
- **INFO-197** [CLI Surface](cli-surface.md) — dynamic-harness entry point, flags, and REPL commands
- **INFO-198** [Runtime Config Schema](runtime-config-schema.md) — dynamic_harness.json sections, defaults, env vars, and layering
- **INFO-199** [Tool Registry Inventory](tool-registry-inventory.md) — The 34 registered tools and how they register
- **INFO-200** [Extension Points](extension-points.md) — Agent classes, reactive policies, tools, and skills
- **INFO-201** [Repo Layout and Build Assets](repo-layout-and-build-assets.md) — src/ layout, prompts, resources, scripts, packaging, config template
<!-- pb:index:end -->
