---
id: INFO-079
type: info
title: G4 — artifact_ids are free-form; written files not linked
summary: P0 (resolved): written files now link to the artifact; read_artifact and provenance surface them.
date: 2026-09-23
status: current
---

# G4 — artifact_ids are free-form; written files not linked

**Severity:** P0. **Status:** resolved.

**Current state:** `deliver_report` copies `files_written` into the artifact
directory, fills `raw_data` from them, and keeps a `files_written.json`
(declared to stored) sidecar. `read_artifact(file=...)` and the provenance
`index.jsonl` surface the stored copies. A parent resolves a child's written
files through the artifact ID.

## Owns
- G4 gap outcome: written files link to the artifact.

## Excludes
- Artifact-system design: `02-architecture/concepts/artifact-system/`.
- Delegation contract: `02-architecture/concepts/delegation-model/`.
