# Layer 03 — Implementation

**With what concrete assets is it realized?**

The runtime is realized in Python 3.10+ under `src/dynamic_harness/` (async actor-model agent runtime, `Runtime` orchestrator, `Agent` loop, ToolRegistry with 25 tools, artifact store, repository/commit layer, config), plus `prompts/` (variant-generation + refinement prompts), `resources/`, `scripts/` (optimization runners), `pyproject.toml` (build/packaging), and `harness.json.example` (layered config template). These assets **stay in place** at the repo root. This layer owns the plugin-readiness investigation (interface economy: ~7 narrow seams, host-agnostic policies, **no loader / no late injection**) and the implementation-side rationale that shapes how those assets are structured.

## Owns
- Repo layout notes, build modules, scripts, model resources
- Interfaces and config conventions (harness.json layering, policy seams)
- Plugin-readiness direction (interface economy, `core/policies/` host-agnostic objects)
- Implementation decisions (ADRs with `IMD` prefix) and rationale

## Excludes
- Scope, capabilities → `01-product/`
- Architecture rationale, organizing design → `02-architecture/`
- Proof criteria, test mechanics → `04-verification/`
- Release policy → `05-operation/`
- Future features → `06-evolution/`

## Contents

- [plugin/](plugin/) — INVESTIGATION.md (Q1–Q7 rulings, interface economy direction, "no loader, ever")

## Pointers (assets that stay at repo root)

- `src/dynamic_harness/` — the runtime source (module map in AGENTS.md)
- `prompts/`, `resources/`, `scripts/`
- `pyproject.toml` — build system, entry point `dynamic-harness = dynamic_harness.cli.terminal:main`
- `harness.json.example` — layered config template (common base `~/.config/dynamic-harness/harness.json` + local overlay)

Implementation status is tracked in `06-evolution/`; verify with the tests in `tests/` (see `../05-operation/runbook.md`).