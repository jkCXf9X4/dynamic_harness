---
id: INFO-197
type: info
title: CLI Surface
summary: dynamic-harness entry point, flags, and REPL commands
date: 2026-10-10
status: current
---

# CLI Surface

Terminal entry point for the runtime. Source: `src/dynamic_harness/cli/terminal.py`.

## Entry
- Console script `dynamic-harness` and `python -m dynamic_harness` both run `dynamic_harness.cli.terminal:main`.
- Positional `prompt` (zero or more words) carries the inline task; `-m FILE` reads it from a file.

## Flags
- `--config PATH` — explicit config file (overrides discovery).
- `--temp` — use temporary directories.
- `--model REF` — root model, `<provider>/<model>` form; first slash splits.
- `--provider ID` — provider from the config's `providers` map; uses the config model when it names this provider, else the provider's first model.
- `--base-url URL` — LLM API base URL override for the active provider.
- `--api-key KEY` — credential override; credentials are never read from the config file.
- `--artifact-dir DIR`, `--repo-dir DIR` — artifact and commit repository locations.
- `--interactive`, `-i` — REPL mode.
- `--resume AGENT_ID` — resume an interrupted/failed agent from its persisted checkpoint.
- `--profile` — profile the live session; writes profile.txt/json + meta.json under the run root.
- `--profile-dir DIR` — profile output directory (default `<run root>/profile`).
- `--profile-interval MS` — sampling interval, default 10.

## Batch mode
- Runs the task to completion; exit code 0 on success, 1 on failure/escalation.
- Non-TTY sessions skip the editor and just await the task.

## REPL mode
- prompt_toolkit input line with a live token counter; the root agent's replies stream above the prompt.
- The agent's `ask` tool swaps the prompt to `[ask] <question>` and returns the typed answer.
- A line starting with `/` is a command; other lines inject into the active root agent.
- Commands: `/help` `/tree` `/agents` `/provenance <id>` `/trace <id>` `/artifacts [id]` `/index` `/checkpoints` `/resume <id>` `/reset` `/compact`, `exit`/`quit`.
- `/resume` and `/reset` are gated while a run is active; `/compact` is not.

## Owns
- The CLI's entry points, flags, and REPL commands.

## Excludes
- Config keys and defaults: `INFO-198`.
- Tool inventory: `INFO-199`.
- Run and test procedures: `INFO-138`.
