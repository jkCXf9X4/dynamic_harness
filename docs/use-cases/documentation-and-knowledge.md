---
title: "Use-Case — Documentation & Knowledge"
category: use-case
summary: >
  Generate or refresh documentation from a codebase, map an API surface, and
  curate a durable reference library. This family leans on read→summarize→write
  flows and progressive disclosure; it also shows how the reference-library
  mechanism (docs/references) becomes content, not just scaffolding.
related:
  - concepts/artifact-system.md
  - concepts/self-healing.md
  - api/artifacts.md
  - ../agent_methodology_guidelines.md
---

# Documentation & Knowledge

Read-only-ish knowledge work where the output is **prose/structured docs
saved as versioned artifacts**, not code changes. Because the "source" is a
codebase the agent must discover and read, the delegation model still governs:
sub-agents each document one module/one surface, and a root synthesizes a
document tree from validated summaries.

## Scenario A — Generate/refresh module docs from code

> "Document the `core/` package. For each public module write a concise markdown
> API page (purpose, key classes/functions, usage snippet, related links) into
> `docs/api-gen/<module>.md`. Then produce an index page. Match the existing
> docs front-matter (title, category, summary, related)."

**Why it fits:** derives facts from code (verifiable by re-reading the source it
    cites), splits cleanly per module into parallel sub-agents, and writes
    durable artifacts. The index page binds separate artifacts together.

**Root decomposition:**

```
core/agent.py    → role "API Documenter" → docs/api-gen/agent.md
core/runtime.py  → role "API Documenter" → docs/api-gen/runtime.md
core/task.py     → role "API Documenter" → docs/api-gen/task.md
tools/           → role "API Documenter" → docs/api-gen/tools.md  (enumerate 19 tools)
          ↓ VERIFY each page names real symbols (read the artifact + spot-check source)
Root: synthesize docs/index.md + report with all ids
```

**Tool flow & constraints:** each documenter uses `read` on its module(s) and
`read` on a sibling doc to match conventions; writes with `write`. Names cited
must exist — a hallucinated function is caught at the root's verification pass
(guidelines: *don't document symbols you haven't seen*).

## Scenario B — Curate the reference library (`docs/references/`)

The framework itself **already exercises this family**: `core/references.py`
discovers `docs/references/` and injects a compact index into the agent
environment; the full rationale is only `read` on demand (progressive
disclosure). A use-case here is an agent maintaining that library: given new
learned guidelines or tool rationale, condense them into a durable reference doc
and refresh the index.

**Why it fits:** it is the intended durability mechanism (survives prompt
optimization), and a maintenance agent selects which existing doc to fold a new
insight into rather than appending to the prompt.

## Scenario C — Concept-time summaries of existing artifacts

After any batch of analysis runs, produce an executive overview. Uses
`hierarchical_summary(artifact_ids, runtime.artifact_store)` to collapse many
artifacts into a structured, indented executive summary, then `write` it.

**Why it fits:** assumes the artifacts exist (from a prior report-heavy run);
this is a **synthesis-only** workload that does not re-discover the tree.

## Verification & acceptance

- For generated API docs: parent confirms each artifact cites real symbols and
  follows the stated conventions; a hallucinated reference is a hard fail.
- For reference-library edits: confirm the new entry's heading matches the doc,
  and that `discover_references()` still lists it (the index is derived).
- Cross-cut claims ("these are the 19 tools") must equal the real registry
  count — verify with `read` of `registration.py` or `list_tools`.

## Fit checklist & caveats

- **Fits well**: bulk API docs, per-module doc pages, reference-library
  maintenance, overview synthesis.
- **Strain**: "write marketing prose about the product" is not verifiable and
  has no code source — weak fit. Keep docs grounded in symbols/files the agent
  actually read.
- **Watch**: source can drift after docs exist; a regeneration requires a
  re-read, not editing the old artifact blindly.