---
title: "Use-Case — Documentation & Knowledge"
category: use-case
summary: >
  Generate or refresh documentation from a codebase, map an API surface, and
  curate a durable reference library — read→summarize→write flows and
  progressive disclosure, with the reference library as content not scaffolding.
related:
  - ../../02-architecture/concepts/artifact-system/README.md
  - ../../02-architecture/concepts/self-healing/README.md
  - ../../../docs/api/artifacts.md
  - ../../02-architecture/methodology/README.md
---

# Documentation & Knowledge

Read-only-ish knowledge work whose output is **prose/structured docs saved as
versioned artifacts**, not code changes. Because the source is a codebase the
agent must discover and read, the delegation model still governs: sub-agents each
document one module/surface, and a root synthesizes a validated document tree.

## Scenario A — Generate/refresh module docs from code

> "Document the `core/` package. For each public module write a concise markdown
> API page (purpose, key classes/functions, usage snippet, related links) into
> `docs/api/<module>.md`. Then produce an index page. Match the existing docs
> front-matter (title, category, summary, related)."

**Why it fits:** derives facts from code (verifiable by re-reading the source it
cites), splits cleanly per module into parallel sub-agents, writes durable
artifacts; the index page binds separate artifacts together.

**Root decomposition:** `core/agent.py`, `core/runtime.py`, `core/task.py`, and
`tools/` each go to a role "API Documenter" writing `docs/api/<module>.md`
(enumerating the tools). Root VERIFYs each page names real symbols (read the
artifact + spot-check source), then synthesizes an index page and reports ids.

**Tool flow:** each documenter `read`s its module(s) and a sibling doc to match
conventions, writes with `write`. Cited names must exist — a hallucinated
function is caught at the root's verification pass (guidelines: *don't document
symbols you haven't seen*).

## Scenario B — Curate the reference library (`docs/references/`)

The framework **already exercises this family**: `core/references.py` discovers
`docs/references/` and injects a compact index; full rationale is `read` on
demand. The use-case is an agent maintaining that library — condensing new
guidelines into a durable doc and refreshing the index (the intended durability
mechanism, folding an insight into the right doc rather than the prompt).

## Scenario C — Concept-time summaries of existing artifacts

After a batch of analysis runs, `hierarchical_summary(artifact_ids,
runtime.artifact_store)` collapses many artifacts into a structured executive
summary, then `write` it — a **synthesis-only** workload over prior artifacts.

## Verification & acceptance

- Generated API docs: the parent confirms each artifact cites real symbols and
  follows the stated conventions; a hallucinated reference is a hard fail.
- Reference-library edits: the new entry's heading matches the doc, and
  `discover_references()` still lists it (the index is derived).
- Cross-cut claims ("these are the 19 tools") must equal the real registry count
  — verify with `read` of `registration.py` or `list_tools`.

## Fit checklist & caveats

- **Fits well**: bulk API docs, per-module doc pages, reference-library
  maintenance, overview synthesis.
- **Strain**: "write marketing prose about the product" is not verifiable and has
  no code source — weak fit. Keep docs grounded in symbols/files actually read.
- **Watch**: source can drift after docs exist; regeneration requires a re-read,
  not editing the old artifact blindly.
