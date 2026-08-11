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
    "repeated_call_limit": 5
  }
}
```

The config file is discovered automatically from `./harness.json` (CWD),
`~/.config/dynamic-harness/harness.json` (XDG user-global), or explicitly via
`--config path/to/harness.json`. If no file is found, defaults are used.

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

Opens the default Rich-rendered interactive REPL. Type a task and press Enter. Live rendering shows the agent tree (left), status, and streaming events.

### Single-Shot Mode

```bash
dynamic-harness "Find the 3 largest Python files in this project"
```

Runs the task and exits. The output shows each agent's actions and final report.

### TUI Mode (most verbose)

```bash
dynamic-harness --tui
```

Launches the Textual TUI. `--tui` is also accepted as the first argument:
- **Left panel:** Tree of agents (green = completed, red = failed, yellow = running)
- **Right panel:** Streaming events from all agents

The TUI and the terminal REPL share a single rendering pipeline
(`cli/present.py` view-models + `cli/render.py` adapters), so agent trees,
status lines, and event formatting are consistent across both interfaces.

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

When an agent completes, you see:

```
Agent abc123 completed:
  Summary: Found 3 files: main.py (245 lines), runtime.py (166 lines), agent.py (409 lines)
  Artifacts: /tmp/artifacts/def456/file_list.json
  Confidence: 0.95
```

### The Task Tree

Every task creates a tree of agents:

```
Root (analyze codebase)
  ├── Security Auditor (completed)
  ├── Test Coverage Checker (completed)
  └── Style Checker (failed — re-delegated)
        └── Style Checker (retry) (completed)
```

### TUI Commands

| Command | Action |
|---------|--------|
| `/help` | Show available commands |
| `/history` | Show task history |
| `/tree` | Show agent task graph |
| `/agents` | Show agent count, commits, tokens |
| `/reset` | Clear all agents and state |
| `/new` | Start a fresh root agent |
| `/kill` | Kill the running agent |
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
Use the `/agents` command in the TUI to see per-agent token usage. If a single agent uses >50K tokens, the task should be decomposed into sub-agents.