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

- `agents.txt` — plain-text agent tree: id, `[status]`, description, cumulative messages, token usage, USD cost markers — own cost (`$`) and subtree cost including all descendants (`Σ$`), from the provider's per-request cost when reported (e.g. OpenRouter) or configured prices as a fallback. Rewritten on every terminal event, so you can tail it while a run is live.
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
└ 3a1f9c02 [completed] analyze codebase (1200t, 14msgs)
  ├ b2e8d4aa [completed] Security Auditor (800t, 9msgs)
  ├ c9f3e771 [completed] Test Coverage Checker (1100t, 12msgs)
  └ d4a5b2ef [failed] Style Checker (300t, 6msgs)
    └ e6f0c113 [completed] Style Checker (retry) (900t, 10msgs)
```

Status + messages + token usage per agent is enough to spot a stuck or looping
prompt at a glance.
