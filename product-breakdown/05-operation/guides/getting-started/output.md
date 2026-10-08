---
id: INFO-112
type: info
title: Understanding the Output
summary: When an agent completes, the CLI shows a compact outcome
date: 2026-09-23
status: current
---

# Understanding the Output

## Agent Reports

When an agent completes, the CLI shows a compact outcome:

```
✓ Agent abc123 completed:
  Found 3 files: main.py (245 lines), runtime.py (166 lines), agent.py (409 lines)
```

Along with a one-line aggregate and the paths to the persisted state files.

## Persisted Overview

The terminal stays prompt-only, but a full, continuously-refreshed overview is
written to the **run directory** (`.dynamic-harness/<timestamp>_<id>/`, the
parent of `artifacts/`, `repo/`, and `traces/`):

- `agents.txt` — plain-text agent tree, two lines per agent: an identity line (id, `[status]`, description, and the profile/model it runs on — the delegated profile tier (`@fast`) or the resolved model id when no profile is set (`@deepseek/deepseek-v4-flash`)) and a metrics line (cumulative messages, token usage, USD cost markers — own cost (`$`) and subtree cost including all descendants (`Σ$`), from the provider's per-request cost when reported (e.g. OpenRouter) or configured prices as a fallback). Live agents also show what they did last and how long ago (`(tool web_search 12s)`) — a climbing age means the agent is mid-call, likely a long LLM request. Rewritten continuously while a run is live (≈1/s heartbeat, plus on every event), so you can tail it and always know how fresh it is.
- `agent_tree.json` — same tree as structured JSON (for machine parsing).
- `stats.json` — aggregate counts (agents, commits, tokens).
- `events.jsonl` — append-only structured event stream (report/failure/escalation/activity).
- `index.jsonl` — flat artifact→agent/task/path map (written after the run when artifacts exist).

This keeps the CLI clean and persists all other data to files, so a
long-running or batch run is fully traceable and inspectable by external tooling
even after the process exits.

## The Task Tree

Every task creates a tree of agents, available on disk as `agents.txt` (updates
continuously) and on demand via `/tree`:

```
└ 3a1f9c02 [✓ completed]  analyze codebase · @deepseek/deepseek-v4-flash
    msgs 14 · tokens 1'200
  ├ b2e8d4aa [✓ completed]  Security Auditor · @fast
    msgs 9 · tokens 800
  ├ c9f3e771 [✓ completed]  Test Coverage Checker · @fast
    msgs 12 · tokens 1'100
  └ d4a5b2ef [✗ failed]   Style Checker · @deepseek/deepseek-v4-flash
    msgs 6 · tokens 300
    └ e6f0c113 [✓ completed]  Style Checker (retry) · @fast
      msgs 10 · tokens 900
```

The status glyph (✓/✗/▶/⚑) is padded so descriptions align across states,
the profile/model marker the agent runs on, and messages + token usage per
agent are enough to spot a stuck or looping prompt at a glance — and to see
at a glance which tier each branch of the tree ran on.
