---
id: INFO-082
type: info
title: G3 — Progressive disclosure is data, not an interface
summary: P0 (resolved): read_artifact takes a level parameter and raw_data is populated from written files.
date: 2026-09-23
status: current
---

# G3 — Progressive disclosure is data, not an interface

**Severity:** P0. **Status:** resolved.

**Current state:** `read_artifact` takes `level`
(`auto|headline|summary|technical|full|raw`) and defaults to the progressive
summary, withholding deeper detail. `raw_data` is populated from written files
in `deliver_report` (`runtime._store_written_files`). An unknown level is an
explicit error.

## Owns
- G3 gap outcome: progressive disclosure is an interface, not just data.

## Excludes
- Artifact-system design: `02-architecture/concepts/artifact-system/`.
