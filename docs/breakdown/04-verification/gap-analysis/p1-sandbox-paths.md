---
id: INFO-086
type: info
title: G5 — Sandbox rejects documented /tmp write patterns
summary: P1 (resolved): examples use workspace-relative paths and artifact references; the sandbox error names the workspace root.
date: 2026-09-23
status: current
---

# G5 — Sandbox rejects documented /tmp write patterns

**Severity:** P1. **Status:** resolved.

**Current state:** the example and config docs
(`02-architecture/examples/`, `docs/api/task.md`,
`02-architecture/concepts/artifact-system/`) no longer instruct `/tmp/...`
writes — they use workspace-relative `outputs/...` paths and artifact
references. The sandbox's outside-workspace error names the workspace root and
suggests a relative path. No default `generated_root` change (it would break
benchmark CWD-relative tasks).

## Owns
- G5 gap outcome: docs and sandbox agree on workspace-relative writes.

## Excludes
- Sandbox implementation: `03-implementation/`.
