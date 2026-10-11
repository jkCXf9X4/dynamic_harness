---
id: INFO-201
type: info
title: Repo Layout and Build Assets
summary: src/ layout, prompts, resources, scripts, packaging, config template
date: 2026-10-10
status: current
---

# Repo Layout and Build Assets

The concrete assets that realize the runtime. All stay at the repo root; this layer only records them.

## src/dynamic_harness/
- Python 3.10+ package; async actor-model runtime.
- Subpackages: `api`, `artifact`, `benchmark`, `cli`, `core`, `llm`, `memory`; `config.py` at the package root.
- `core/`: `agent.py`, `runtime.py`, `tools/`, `policies/`, `comms/`, `checkpoint.py`, `context.py`, `events.py`, `events_format.py`, `prompts.py`, `references.py`, `result_store.py`, `spawn_limits.py`, `task.py`, `telemetry.py`, `trace.py`, `usage.py`, `tool_context.py`, `environment.py`, `agent_system_prompt.txt`.
- `cli/`: `terminal.py` (entry), `common.py`, `present.py`, `profile.py`, `state.py`.

## Root assets
- `prompts/`: `code_review.txt`, `file_inventory.txt`, `generate_variants.prompt`, `refine_variants.prompt`, `security_audit.txt`.
- `resources/`: `_collab`, `_parallel`, `_payload`, `_sources`.
- `scripts/`: `cache_probe.py`, `diagnose_cache.py`, `run_optimize.py`, `run_prune_ab.py`.
- `pyproject.toml`: name `dynamic-harness`, version 0.1.0, `requires-python >=3.10`, entry point `dynamic-harness = dynamic_harness.cli.terminal:main`.
- `dynamic_harness.json.example`: layered config template (XDG base + local overlay).

## Owns
- The repo layout and build/packaging facts.

## Excludes
- CLI behavior: `INFO-197`.
- Config schema: `INFO-198`.
- Build and release steps: `INFO-137`.
