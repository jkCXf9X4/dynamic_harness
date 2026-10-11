---
id: INFO-132
type: info
title: Rate Limits & Provider Quirks
summary: Free-tier models hit per-minute rate limits mid-run; use a paid/served model for full runs and `provider_ignore` for tool-refusing providers
date: 2026-09-23
status: current
---

# Rate Limits & Provider Quirks

- Free-tier models (e.g. `:free` suffixes) hit per-minute rate limits and abort
  mid-run with `openai.RateLimitError: 429`. Use a paid/served model for full
  runs.
- `provider_ignore` routes around OpenRouter providers that mishandle tool
  calls. If the orchestrator returns empty output instead of tool calls, a
  guessed provider is refusing tools — add it to `provider_ignore`.
- Some models emit the **identical** `write()` call repeatedly. The harness
  fails that sub-agent after 5 identical batches (safety), and the `write` tool
  now returns a `"No change: content identical..."` message on identical content
  (`src/dynamic_harness/core/tools/filesystem.py:write`) so agents recover
  instead of spinning.

## Owns
- Free-tier rate limits and the paid/served-model requirement for full runs
- `provider_ignore` routing for tool-refusing OpenRouter providers
- The repeated-identical-`write()` safety behavior

## Excludes
- Where `harness.json` lives and its default config: `INFO-130`
