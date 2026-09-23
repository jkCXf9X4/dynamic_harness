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
