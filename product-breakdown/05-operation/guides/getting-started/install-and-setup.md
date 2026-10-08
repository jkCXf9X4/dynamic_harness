---
id: INFO-111
type: info
title: Install & Environment
summary: Python 3.10 or later
date: 2026-09-23
status: current
---

# Install & Environment

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

## API Key

The API key is read from the environment, so add it to your shell config:

```bash
# ~/.bashrc or ~/.zshrc
export OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

Then reload: `source ~/.bashrc`.

For OpenAI directly:

```bash
# ~/.bashrc or ~/.zshrc
export OPENAI_API_KEY=sk-your-key-here

# dynamic_harness.json
{"root_model": "openai/gpt-4o", "providers": {"openai": {"env": ["OPENAI_API_KEY"], "base_url": "https://api.openai.com/v1"}}}
```
