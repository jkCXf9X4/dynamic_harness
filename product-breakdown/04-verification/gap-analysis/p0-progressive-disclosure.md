---
title: "G3 — Progressive disclosure is data, not an interface"
category: meta
summary: >
  P0 (resolved): read_artifact returned every view at once and raw_data was dead,
  so the lazy-load economics were unachievable in the tool loop.
parent: "README.md"
---

# G3. Progressive disclosure is data, not an interface; `raw_data` is dead

**Severity:** P0 — breaks a core promise. **Status:** RESOLVED.

**Concept promise:** a six-level disclosure ladder — headline → 200-char →
1000-char → technical → full → raw, with parents "reading summaries first and
progressively load[ing] more detail as needed"
(`../../02-architecture/concepts/artifact-system.md:22-61`).

**Implementation (before):** `read_artifact` returned **every non-empty view in
one response** (`tools/agents.py:224-230`). There was no way to ask for "just the
headline" or "just the 1000-char summary", so the lazy-load economics (300-token
preview vs 30K dump) were not achievable *in the tool loop* — a parent that
called `read_artifact` on a big child got the full report whether it wanted it or
not. Separately, `ArtifactView.raw_data` was **never written anywhere**
(`runtime.py:429-435` fills only headline/summary_200/summary_1000/technical/
full_report); the `raw_data` view was read but always empty — the ladder
effectively had five steps.

**Breaks:** the cost story of `repository-analysis` and
`research-and-synthesis` (parents consuming summaries cheaply), and
`documentation-and-knowledge` Scenario C's `hierarchical_summary`.

**Fix direction:** add a `level` parameter to `read_artifact`
(`headline|summary|technical|full|raw`), populate `raw_data` from a child's
`files_written` payload or the sidecar, and make the default level `summary`.

**Status:** RESOLVED — `read_artifact` gained `level`
(`auto|headline|summary|technical|full|raw`) and now defaults to the progressive
summary (deeper detail withheld). `raw_data` is populated from written files in
`deliver_report` (`runtime._store_written_files`). An unknown level is an
explicit error.
