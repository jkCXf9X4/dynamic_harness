---
title: "Use-Case — Research & Synthesis"
category: use-case
summary: >
  Gather external information and synthesize it into a durable, source-cited
  artifact: competitive research, feature/API documentation, and comparison
  write-ups. Exercises `webfetch` and parallel sub-agents, with careful
  discipline around the fetcher's restrictions and the "summary is a preview,
  the artifact is the truth" rule.
related:
  - concepts/delegation-model.md
  - concepts/artifact-system.md
  - api/artifacts.md
  - ../references/tool_motivations.md
---

# Research & Synthesis

The knowledge needed to answer lives **outside the workspace** and must be
fetched, condensed, and turned into a cited artifact. The workhorse tool is
`webfetch` — restricted to public non-private hosts (no loopback/private/SSRF
targets), capped at 200 KB per page, following up to 3 redirects. Because
pulling many pages into a single agent context is precisely the context-rot
shape the framework avoids, research load is fanned out to parallel
sub-agents, each returning only a short extract.

## Scenario — Build-vs-buy cache comparison

> "Produce a build-vs-buy comparison for our cache layer. Compare two
> open-source cache engines and one managed offering across: eviction policies,
> snapshot/durability, operational notes, and ops burden. Cite every claim
> with the URL you actually fetched. Write the result to
> `reports/cache_compare.md` and report with that artifact."

**Why it fits:** the work is fetch-one-by-one + cite, it splits naturally into
one sub-agent per source, and the output is a versioned **citable artifact**.
The citation URLs are the artifacts of proof — matching the framework rule that
a summary is only a preview and the artifact is the truth.

## Root decomposition

```
Open engine A    → role "Researcher" → fetch doc page, extract eviction/write facts → src_a.md
Open engine B    → role "Researcher" → fetch doc page, extract eviction/write facts → src_b.md
Managed option  → role "Researcher" → fetch pricing + feature pages          → src_mgd.md
       ↓ VERIFY each artifact cites URLs the agent actually fetched (re-fetch a sample)
Root: build `reports/cache_compare.md`, every row backed by a URL, report with all ids
```

**Constraints:** the fetcher cannot reach private/localhost ranges and truncates
pages at 200 KB — a researcher that hits a truncation marks it rather than
inventing the remainder. Use `webfetch` for network work; `bash` is not a
fetch proxy.

## Factual discipline & citation

- **Citation is the artifact**: no URL cited unless the agent actually fetched
  it; parent re-fetches a sample to confirm a live source.
- **Do not fill gaps from memory**: truncated or blocked pages are marked; the
  parent asks for a source URL before accepting the claim (guideline *verify,
  do not synthesize*).
- A blocked source → that slot is `converse`d (re-sub) or, if truly unreachable,
  resolved as un-rated rather than guessed (Layer-1 resume / Layer-4 escalate).

## Fit checklist & caveats

- **Fits well**: small per-slot research with cite-and-verify discipline;
  external feature/API docs; comparison with a checkable source.
- **Strain**: a "fetch 50 listings" job bloats even a fresh sub-agent — split
  per page/source and return extracts only; a large harvest is a pipeline job
  (see [pipelines-and-jobs.md](pipelines-and-jobs.md)) needing `prune`/`restore`
  to avoid rot.
- **Not a fit**: unstructured "give me opinions" with no citation ground-truth —
  the outcome is unverifiable prose.