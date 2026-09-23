---
title: "Result Handles — Caching Behind Opaque Read-Only Handles"
category: meta
summary: >
  Every cacheable tool call stores its full output behind an opaque handle;
  result_read pages it and result_bash pipes it to a shell's stdin, never
  re-executing the producing tool.
parent: "README.md"
---

# Result Handles

Every cacheable tool call (`read`, `glob`, `grep`, `bash`, `webfetch`,
`read_artifact`, `status`, `usage`, …) stores its **full** output in a per-agent,
bounded, in-memory `ResultStore` behind an opaque handle. When a result is
truncated, the footer advertises the handle and the read-only `result_read` tool
pages the snapshot by `result_id` — **never re-executing** the producing tool, so
paging a slow bash/webfetch result is free. `result_bash` goes further: it pipes
the snapshot text to any shell command's stdin (`rg`, `jq`, `awk`, `wc -l`,
`python3 -c '...'`), so the full bash vocabulary probes an expensive saved output
without re-running the work.

Two properties follow:

- **Handles are always read-only.** A fresh result means calling the work tool
  again (work tools accept no `result_id` input), enforced in the registry's
  mutator-set logic.
- **Memory-only, cleared on GC/reset.** A resumed agent never sees stale
  snapshots; an unknown handle errors with "re-run the producing tool".

This is a distinctive cost/context optimization (`core/result_store.py`).
