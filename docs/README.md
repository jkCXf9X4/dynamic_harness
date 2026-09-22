# docs/ — Runtime-Coupled Documentation

This directory holds only **runtime-coupled** content — documentation that the
runtime itself loads or that describes the runtime's public surface. It is
intentionally small and should stay that way.

## What lives here

- `api/` — module-level API reference generated for the runtime surface
  (agent, runtime, task, tools, artifacts, repository, llm, config, policies).
- `references/` — the durable rationale library loaded by the runtime's own
  agent system prompt (see `src/dynamic_harness/core/references.py`,
  `DEFAULT_REFERENCES_DIR = "docs/references"`), plus the skill/template docs
  that govern the product-breakdown convention.

## What does NOT live here

The repo's **definition state** — the layered product breakdown (intent,
product, architecture, implementation, verification, operation, evolution) —
lives in [`product-breakdown/`](../product-breakdown/README.md). VISION,
requirements, methodology, concepts, examples, use-cases, gap-analysis, and
guides all moved there.

## Why the split is intentional

`docs/references/` is loaded by the runtime's agent system prompt, so it must
stay at a stable, runtime-known path. `docs/api/` documents the runtime surface
and is regenerated from code. Everything that answers a *definition* question
(why, what, how-organized, proof, operation, evolution) belongs in
`product-breakdown/`. This split is deliberate — do not "fix" it by moving
files back into `docs/`.