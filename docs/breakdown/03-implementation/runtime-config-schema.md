---
id: INFO-198
type: info
title: Runtime Config Schema
summary: dynamic_harness.json sections, defaults, env vars, and layering
date: 2026-10-10
status: current
---

# Runtime Config Schema

The runtime config. Source: `src/dynamic_harness/config.py` (pydantic models).

## File and layering
- Filename `dynamic_harness.json`; loader `load_harness_config(path)`; no file found means all defaults.
- Layering: XDG base `~/.config/dynamic_harness/dynamic_harness.json` (or `$XDG_CONFIG_HOME/dynamic_harness/`) under a local `./dynamic_harness.json` overlay; `--config PATH` adds an explicit file on top; deep merge (nested dicts field by field, scalars/lists replace).

## Top-level keys
- `root_model` (default `openrouter/deepseek/deepseek-v4-flash`, legacy `model` alias) plus sections `llm`, `providers`, `profiles`, `safety`, `self_heal`, `agent`, `communication` (below).

## providers
- Keyed by provider id; model ref `<provider>/<model>` splits on the first slash.
- `env` — ordered env var names, first set wins; credentials come from the environment only, never the config file.
- `base_url` — OpenAI-compatible endpoint; `provider_force` / `provider_ignore` / `provider_allow_fallbacks` — OpenRouter routing.
- `models` — catalog map; `model_id` remaps the upstream id; `limit` and `cost` are metadata.
- Built-in openrouter: env `OPENROUTER_API_KEY`, `OPENAI_API_KEY`; base_url `https://openrouter.ai/api/v1`.

## llm (defaults)
- `verify_ssl` true, `call_timeout_seconds` 500, `stream` true, `fallback_on_rate_limit` true.
- Retries: `retry_max_attempts` 4, `rate_limit_max_attempts` 6, base delay 1.0s, cap 30s, jitter 0.5s, rate-limit multiplier 3.0.
- `gateway_timeout_prompt_budget` 20000, `gateway_timeout_max_tokens` 4096.

## safety (defaults)
- `max_iterations` 400, `timeout_seconds` 7200, `disable_root_timeout` true, `max_agents` 300, `max_depth` 15.
- `max_agent_tokens` null, `max_same_target_delegations` 0, `repeated_call_limit` 5, `repeated_recovery_attempts` 2.
- Repeated-call exempt tools: status, usage, result_read, result_bash, channels, channel_info, channel_read.
- `near_identical_threshold` 3, `near_identical_window` 6, `near_identical_similarity` 0.6, `near_identical_tools` [bash], `iteration_warning_margin` 50.
- `context_fill_warning_tokens` 100000, `context_auto_compact_tokens` 240000.

## self_heal / agent / communication (defaults)
- `self_heal`: `mode` true, `max_resumes` 1, `max_fresh_retries` 1.
- `agent`: `environment_notes` [], `references_dir` null, `skills_dir` null, `active_turn_window` 50, `stream_children` true.
- `communication`: `topology` off (off|relay|siblings|shared|topics), `registration` parent, `shared_topic` shared, `channels` [], `digest_mode` pull, `digest_max_items` 5, `digest_max_tokens` 400, `trace` true.

## Owns
- Config keys, defaults, env vars, and layering.

## Excludes
- Why the knobs exist: `02-architecture/`.
- CLI flags that override config: `INFO-197`.
