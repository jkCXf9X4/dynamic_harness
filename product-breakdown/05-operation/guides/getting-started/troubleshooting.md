---
id: INFO-115
type: info
title: Common Issues
summary: Ensure or is set in your shell config (e.g. ), or pass on the command line
date: 2026-09-23
status: current
---

# Common Issues

### "No API key" error

Ensure `OPENROUTER_API_KEY` or `OPENAI_API_KEY` is set in your shell config
(e.g. `~/.bashrc`), or pass `--api-key` on the command line.

### Missing dynamic_harness.json

If you rely only on defaults or the common base, no local
`dynamic_harness.json` is needed — settings come from
`~/.config/dynamic_harness/dynamic_harness.json` (common base) plus built-in
defaults. To override per-project, copy `dynamic_harness.json.example` to
`dynamic_harness.json` and edit. Without any file, sensible defaults are used
(deepseek-v4-flash on OpenRouter).

### Agent runs forever

If an agent exceeds 400 turns or makes 5 identical tool calls, it is
force-failed. The task was likely too broad — try decomposing it into smaller
pieces.

### High token costs

Use `/tree` (or `agents.txt`) to see per-agent token usage, or `/agents` for the
running total. If a single agent uses >50K tokens, the task should be decomposed
into sub-agents.
