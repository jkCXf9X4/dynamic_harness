---
title: "Getting Started"
category: guide
difficulty: beginner
summary: >
  Quick start guide for Dynamic Harness. Covers installation, environment
  setup, running your first task, and understanding the output.
related:
  - api/runtime.md
  - api/agent.md
  - concepts/delegation-model.md
---

# Getting Started

## Prerequisites

- Python 3.10 or later
- An OpenRouter API key (or OpenAI API key)
- uv (recommended) or pip

## Installation

```bash
git clone <repo-url> dynamic_harness
cd dynamic_harness
uv sync
```

Or with pip:

```bash
pip install -e .
```

## Environment Setup

The API key is read from the environment, so add it to your shell config:

```bash
# ~/.bashrc or ~/.zshrc
export OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

Then reload: `source ~/.bashrc`.

Configurable settings (model, base URL, provider blacklist, safety limits) are managed
in a separate `harness.json` file. Copy the template:

```bash
cp harness.json.example harness.json
```

Edit as needed:

```json
{
  "llm": {
    "model": "deepseek/deepseek-v4-flash-0731",
    "base_url": "https://openrouter.ai/api/v1",
    "provider_ignore": ["gmicloud", "SiliconFlow", "Baidu"],
    "provider_allow_fallbacks": true
  },
  "safety": {
    "max_iterations": 500,
    "repeated_call_limit": 5,
    "max_agent_tokens": 50000
  }
}
```

`max_agent_tokens` (optional) force-fails an agent once its total cumulative
usage (prompt + completion) passes the cap. It is surfaced to agents as a
static budget line, and the `usage` tool lets any agent read its own live
message/token counters — so a tight per-agent goal (e.g. **under 50,000
tokens**) can be communicated both up-front and as the agent runs, without
adding a per-turn observation message.

The config file is discovered automatically from `./harness.json` (CWD),
`~/.config/dynamic-harness/harness.json` (XDG user-global), or explicitly via
`--config path/to/harness.json`. If no file is found, defaults are used.

Every setting — including all the safety, self-heal, and agent keys shown below and
more — is documented in the [Configuration Reference](../api/config.md), with defaults
and the `0`/`null` "cap disabled" convention.

For OpenAI directly:

```bash
# ~/.bashrc or ~/.zshrc
export OPENAI_API_KEY=sk-your-key-here

# harness.json
{"llm": {"model": "gpt-4o", "base_url": "https://api.openai.com/v1"}}
```

## Your First Task

### Interactive Terminal (default)

```bash
dynamic-harness
```

Opens the prompt-only interactive terminal. Type a task and press Enter.
During the run a single live line shows a **token counter** + the current
activity, and the `>>>` input stays **always available**: type a command (e.g.
`/tree` for a live status snapshot) or send a message to the running agent —
it is queued while the agent works and applied immediately when the agent is
waiting on its children. Final outcome prints at the end; everything else — the
agent tree, status, and event stream — is persisted to files under the run
directory for telemetry and automated inspection (see [Persisted Overview](#persisted-overview)).

### Single-Shot Mode

```bash
dynamic-harness "Find the 3 largest Python files in this project"
```

Runs the task headlessly, prints the final outcome + aggregate, and writes the
run's persisted overview (agents/tree/stats/events) to `.dynamic-harness/<ts>_<id>/`.

### Interactive REPL

```bash
dynamic-harness
```

Opens the prompt-only interactive terminal: type a task, or use `/help` for
commands (`/tree`, `/agents`, `/provenance`, `/reset`, `exit`/`quit`).
Continues the same root agent across turns so you can iterate on a task in one
conversation.

### No-LLM Mode (testing)

```bash
dynamic-harness --no-llm "test without AI"
```

Runs without an LLM. Because no LLM is configured, the agent immediately
**fails** with `"No LLM provider configured"`. Useful for verifying the
runtime/tool infrastructure without API costs, but it does **not** produce a
report — expect a failure, not a summary.

## Understanding the Output

### Agent Reports

When an agent completes, the CLI shows a compact outcome:

```
✓ Agent abc123 completed:
  Found 3 files: main.py (245 lines), runtime.py (166 lines), agent.py (409 lines)
```

Along with a one-line aggregate and the paths to the persisted state files.

### Persisted Overview

The terminal stays prompt-only, but a full, continuously-refreshed overview is
written to the **run directory** (`.dynamic-harness/<timestamp>_<id>/`, the
parent of `artifacts/`, `repo/`, and `traces/`):

| File | Content |
|------|---------|
| `agents.txt` | Plain-text agent tree: id, `[status]`, description, messages, token usage — one line per agent. Rewritten on every terminal event, so you can tail it while a run is live. |
| `agent_tree.json` | Same tree as structured JSON (for machine parsing). |
| `stats.json` | Aggregate counts (agents, commits, tokens). |
| `events.jsonl` | Append-only structured event stream (report/failure/escalation/activity). |
| `index.jsonl` | Flat artifact→agent/task/path map (written after the run when artifacts exist). |

This mirrors the project direction of keeping the CLI clean and persisting all
other data to files, so a long-running or batch run is fully traceable and
inspectable by external tooling even after the process exits.

### The Task Tree

Every task creates a tree of agents. The same tree is available in two forms
for a quick status/message/token overview:

- on disk as `agents.txt` (updates continuously during the run), and
- on demand in the terminal via `/tree`:

```
└ 3a1f9c02 [completed] analyze codebase (1200t, 14msgs)
  ├ b2e8d4aa [completed] Security Auditor (800t, 9msgs)
  ├ c9f3e771 [completed] Test Coverage Checker (1100t, 12msgs)
  └ d4a5b2ef [failed] Style Checker (300t, 6msgs)
    └ e6f0c113 [completed] Style Checker (retry) (900t, 10msgs)
```

Status + messages + token usage per agent is enough to spot a stuck or looping
prompt at a glance.

### Terminal Commands

| Command | Action |
|---------|--------|
| `/help` | Show available commands |
| `/tree` | Print the agent tree (status/messages/tokens) |
| `/agents` | Show agent count, commits, tokens |
| `/provenance <id>` | Map an agent to its trace/artifacts/commits |
| `/artifacts [id]` | List artifacts (optionally filter by agent) |
| `/checkpoints` | List persisted (resumable) agents |
| `/resume <id>` | Resume an agent from its checkpoint |
| `/index` | Write the run's `index.jsonl` |
| `/reset` | Clear all agents and state |
| `exit` | Quit |

## Next Steps

1. Read the [agent methodology guidelines](../agent_methodology_guidelines.md) to understand how agents work
2. Try delegating sub-tasks explicitly: `"Read src/core/runtime.py and write a summary to /tmp/summary.txt"`
3. Learn about [programmatic usage](programmatic-usage.md) to embed Dynamic Harness in your apps
4. Explore [custom agents](custom-agents.md) and [custom tools](extending-tools.md)
5. Read the [architecture overview](../VISION.md) for design philosophy

## Common Issues

### "No API key" error
Ensure `OPENROUTER_API_KEY` or `OPENAI_API_KEY` is set in your shell config (e.g. `~/.bashrc`), or pass `--api-key` on the command line.

### Missing harness.json
Copy `harness.json.example` to `harness.json` and edit to your needs. Without it, sensible defaults are used (deepseek-v4-flash on OpenRouter).

### Agent runs forever
If an agent exceeds 500 turns or makes 5 identical tool calls, it's force-failed. The task was likely too broad — try decomposing it into smaller pieces.

### High token costs
Use `/tree` (or `agents.txt`) to see per-agent token usage, or `/agents` for the
running total. If a single agent uses >50K tokens, the task should be
decomposed into sub-agents.