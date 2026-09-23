---
title: "G5 — Sandbox rejects documented /tmp write patterns"
category: meta
summary: >
  P1 (resolved): examples told agents to write to /tmp, which the sandbox always
  rejects, while the default CLI sandbox was the user's whole CWD.
parent: "README.md"
---

# G5. Sandbox rejects the documented `/tmp/...` write patterns

**Severity:** P1. **Status:** RESOLVED (doc + own sandbox).

**Concept/docs:** `../../02-architecture/examples/delegation_descriptions.md`,
`../../02-architecture/examples/task_framing.md`,
`../../02-architecture/concepts/artifact-system.md` all instructed agents to
"write to `/tmp/security_findings.json` and report with the artifact path".

**Implementation (before):** `write`/`edit` resolve absolute paths and reject
anything outside `generated_root`/CWD with `"Path ... is outside the workspace"`
(`tools/filesystem.py:96-105`). Under the default CLI the sandbox **is the user's
CWD** (`cli/common.py` never sets `generated_root`), so `/tmp/...` always failed —
and conversely the agent could freely overwrite the user's own project files. Two
distinct problems: doc drift (examples fail as written) and a weak default
sandbox (no output isolation).

**Breaks:** anyone copy-pasting the examples; the safety story in the use-cases.

**Fix direction:** make the examples use workspace-relative paths + artifact IDs;
consider a default `generated_root` (e.g. `.dynamic-harness/out/`) for CLI runs
so agents don't write into the source tree by default.

**Status:** RESOLVED (doc + own sandbox). The example/config docs
(`../../02-architecture/examples/*.md`, `../../../docs/api/task.md`,
`../../02-architecture/concepts/artifact-system.md`) no longer instruct `/tmp/...`
writes — they use workspace-relative `outputs/…` paths and artifact references.
The sandbox's outside-workspace error now names the workspace root and suggests a
relative path (no default `generated_root` change, which would break benchmark
CWD-relative tasks).
