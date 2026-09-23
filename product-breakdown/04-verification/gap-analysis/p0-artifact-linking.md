---
title: "G4 — artifact_ids are free-form; written files not linked"
category: meta
summary: >
  P0 (resolved): two disjoint stores meant a parent could not resolve a raw file
  path and the substantive file was never surfaced through read_artifact or
  provenance.
parent: "README.md"
---

# G4. `artifact_ids` are free-form strings; agent-written files are not linked to the artifact

**Severity:** P0 — breaks a core promise. **Status:** RESOLVED.

**Concept promise:** artifacts are "the primary communication mechanism" — a
parent resolves a child's output via its artifact ID
(`../../02-architecture/concepts/artifact-system.md:16`,
`../../02-architecture/concepts/delegation-model.md:126-141`).

**Implementation (before):** there were **two disjoint stores**:
- report *metadata* (the `Artifact`) under `artifact_root/<uuid>/`, indexed by
  artifact **UUID**;
- the agent's *actual findings files* under `generated_root` (the sandbox).

`read_artifact(id)` resolved a UUID, or fell back to resolving an **agent id**
(`tools/agents.py:206-223`) — a raw **file path** (which the docs and examples
use as `artifact_ids`, e.g. `/tmp/findings.json`) would not resolve. Worse, the
run `index.jsonl` mapped each artifact to the *metadata* directory
(`runtime.py:586`), and `files_written.json` was stored but **never surfaced**
through `read_artifact` or `provenance`. So "the artifact is the truth" was only
true for the 300-token summary — the substantive file was reachable only by the
parent guessing a path and using `read`.

**Breaks:** every artifact-driven use-case at the "parent reads the child's
actual output" step (`repository-analysis` §Verification, `change-and-validation`
§Verification), and the evaluation/provenance story.

**Fix direction:** write agent `write()` output under the *artifact* directory
(or copy/link it at `deliver_report` time using `payload.files_written`), and
make `read_artifact`/`provenance`/`index.jsonl` surface those files.

**Status:** RESOLVED — `deliver_report` now copies `files_written` into the
artifact directory, fills `raw_data` from them, keeps a `files_written.json`
(declared→stored) sidecar, and `read_artifact(file=...)` + the provenance
`index.jsonl` surface the stored copies.
