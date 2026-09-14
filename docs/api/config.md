---
title: "Configuration Reference (harness.json)"
category: api
module: dynamic_harness.config
summary: >
  Every setting in the `harness.json` config file — the four sections
  (`llm`, `safety`, `self_heal`, `agent`), their default values, the
  disabled-by-`0`/`None` convention, and how each setting maps to runtime /
  agent behavior.
related:
  - api/runtime.md
  - api/llm.md
  - guides/getting-started.md
  - concepts/self-healing.md
---

# Configuration

All runtime behavior is configured through a single JSON file, `harness.json`, loaded by
`config.load_harness_config()`. This document is the canonical reference for every setting.

## How the Config File Is Found

Config is loaded from a **layered merge** of (up to) two files, from lowest to
highest priority — the *common base* is always applied first, then the *local
overlay* overrides it on a per-key basis:

1. **Common base:** `~/.config/dynamic-harness/harness.json` (XDG user-global,
   shared across all your projects).
2. **Local overlay:** `./harness.json` (current working directory), or an
   explicit `--config path/to/harness.json`.

The two files are deep-merged: section objects (`llm`, `safety`, `self_heal`,
`agent`) merge field-by-field, so a local config can override a single setting
(e.g. just `safety.max_iterations`) while keeping every other value from the
common base. Scalar and list fields are replaced wholesale by the overlay — a
local `provider_ignore` list replaces the base's list entirely.

If no file exists at a given level, that level is skipped and the next one
applies:

- XDG common base + local overlay → merged (local wins on conflicts)
- XDG common base only → base applies
- local overlay only → overlay applies
- neither → built-in defaults (no file needed)

If no file is found at all, sensible defaults are used. All fields are optional
— an empty `harness.json` (`{}`) is valid and yields the defaults below.

> **Defaults are the single source of truth.** A bare `Runtime()` (no `config`
> passed) now constructs the same defaults as a default `HarnessConfig()` —
> there is no second fallback dictionary in the runtime (the old `if config else
> <n>` ladder is gone). Config-derived decisions are made by the policy objects
> in `core/policies/`, and their constructors only ever receive config values; a
> `None` config simply yields the `HarnessConfig()` defaults (e.g. via
> `AgentPolicy.from_config(None)`).

The config is validated with Pydantic. Invalid JSON in any file raises
`ValueError` naming that file; invalid field values (out-of-range, wrong type)
fail model validation with a clear message.

Unknown keys are ignored (forward-compatible). The API key is **never** stored in the
config file — it comes from the `OPENROUTER_API_KEY` or `OPENAI_API_KEY` environment
variable instead.

## Overview

```json
{
  "llm": { ... },
  "safety": { ... },
  "self_heal": { ... },
  "agent": { ... }
}
```

A recurring convention: a setting that controls a cap treats **`None` as disabled**, and
— where the field allows it — **`0`** as well. The runtime normalizes caps to `None`
when the configured value is falsy, so an allowed `0` means "no cap", not "cap of zero"
(which would forbid everything). Not every cap field accepts `0` in config validation:
`max_agent_tokens` and `max_same_target_delegations` are `ge=0`, so `0` is a valid way
to disable them in JSON; `max_agents`, `max_depth`, and `timeout_seconds` require a
positive value or `null`, so only `null` disables those. Per-cap notes call this out.

---

## `llm` — LLM provider

| Key | Default | Description |
|-----|---------|-------------|
| `model` | `deepseek/deepseek-v4-flash` | Model identifier sent to the provider. |
| `base_url` | `https://openrouter.ai/api/v1` | Provider endpoint. Point at `https://api.openai.com/v1` to use OpenAI directly. |
| `provider_ignore` | `[]` | OpenRouter provider slugs to exclude (blacklist). |
| `provider_allow_fallbacks` | `true` | Let the provider fall back to other models when the primary is unavailable. |
| `provider_force` | `null` | OpenRouter provider slug to pin exclusively. Setting this disables fallbacks. |
| `verify_ssl` | `true` | Verify TLS certificates on LLM requests. |
| `price_input_per_mtok` | `null` | USD per 1M input tokens, if known (used for cost reporting). |
| `price_output_per_mtok` | `null` | USD per 1M output tokens, if known (used for cost reporting). |
| `call_timeout_seconds` | `500.0` | Timeout for a single LLM request. Must be `> 0`. A slow/stuck provider call is abandoned after this; the agent may retry transient failures. This is a *per-call* deadline and is separate from `safety.timeout_seconds` (the whole-run wall clock). |
| `retry_max_attempts` | `4` | How many times a single LLM call may be retried after a generic transient failure (timeout, connection drop, 5xx) before it is given up. Each retry sleeps an exponential backoff (`retry_base_delay_seconds`, capped by `retry_max_delay_seconds`). Rate-limited calls get their own, larger budget (`rate_limit_max_attempts`). |
| `rate_limit_max_attempts` | `6` | How many times a single LLM call may be retried after a rate limit (HTTP 429 / `engine_overloaded`). Shared upstream pool overloads can outlast the generic transient-error budget, so rate limits get more attempts and a longer backoff (`rate_limit_backoff_multiplier`). |
| `retry_base_delay_seconds` | `1.0` | Base sleep before the first retry. The delay grows exponentially (`base * 2^attempt`), is capped at `retry_max_delay_seconds`, is extended by a provider `Retry-After` header when one is sent, and gets up to `retry_jitter_seconds` of random jitter. |
| `retry_max_delay_seconds` | `30.0` | Upper bound on any single retry sleep. Prevents a long retry chain from stalling a bounded agent for minutes (`safety.timeout_seconds` still caps the whole run). |
| `retry_jitter_seconds` | `0.5` | Maximum random jitter added to each retry sleep, so concurrent agents do not retry in lockstep against a struggling provider. |
| `rate_limit_backoff_multiplier` | `3.0` | Scales the exponential backoff for rate-limited calls. With the defaults the sleeps run ~3s, 6s, 12s, 24s, then the 30s cap — buying a shared upstream pool tens of seconds to shed its overload. |
| `fallback_on_rate_limit` | `true` | On a rate-limited call, retry **without** the session-pinned provider (the `session_id` that normally keeps every turn of a conversation on one provider for a warm prompt cache), so OpenRouter can route the retry to a different provider. Only the retried calls drop the pin — the next turn resumes normal session pinning. No effect when `provider_force` already pins one provider. |

Example:

```json
{
  "llm": {
    "model": "deepseek/deepseek-v4-flash-0731",
    "base_url": "https://openrouter.ai/api/v1",
    "provider_force": "DeepInfra",
    "provider_ignore": ["gmicloud", "SiliconFlow", "Baidu"],
    "provider_allow_fallbacks": true,
    "verify_ssl": true,
    "call_timeout_seconds": 500,
    "retry_max_attempts": 4,
    "rate_limit_max_attempts": 6,
    "rate_limit_backoff_multiplier": 3.0
  }
}
```

> Note: `provider_force` pins every request to one provider (disabling fallbacks), so
> `fallback_on_rate_limit` has no effect while it is set — the extra patience in
> `rate_limit_max_attempts`/`rate_limit_backoff_multiplier` still helps it wait out
> the overloaded upstream pool.

---

## `safety` — loop, timeout, token, and delegation caps

### Loop termination

| Key | Default | Description |
|-----|---------|-------------|
| `max_iterations` | `400` | Hard cap on agent loop iterations. Exceeding it force-fails the agent. |
| `repeated_call_limit` | `5` | Hard cap on *identical* consecutive tool-call batches before the agent force-fails (prevents LLM loops). |
| `repeated_recovery_attempts` | `2` | How many times a looping agent is nudged ("you are repeating yourself, change strategy") before repeated-call detection force-fails it. `0` fails immediately on first detection. |
| `repeated_call_exempt_tools` | `["status", "usage", "result_read", "result_bash"]` | Tool names ignored for pure monitoring: status/usage are cheap live observations; `result_read`/`result_bash` are read-only paging/filtering of already-cached result snapshots (never re-execute work). A turn made up solely of these is not counted toward loop detection (genuinely stuck agents are still bounded by `max_iterations` / `max_agent_tokens` / `timeout_seconds`). |
| `near_identical_threshold` | `3` | Soft-warning threshold: how many near-identical tool calls must appear in the sliding window before a notice is injected. Must be `>= 1`. A notice is non-fatal on its own. |
| `near_identical_window` | `6` | Sliding-window size over which near-identical calls are counted; older calls are forgotten. Must be `>= 2`. |
| `near_identical_similarity` | `0.6` | Minimum `difflib.SequenceMatcher` ratio (`0.0`–`1.0`) between two normalized calls to count as near-identical. Pagination knobs (`token_offset`/`token_limit`) are excluded from the signature so paged reads never look duplicated. Must be in `(0.0, 1.0]`. |
| `near_identical_tools` | `["bash"]` | Tool names monitored for near-identical repetition. Scoped to `bash` by default (the observed churn loop). Bash signatures are pagination-normalized (`sed -n 'A,Bp'` / `awk NR>=A&&NR<=B` / `head -N` collapse to a family), and same-file overlapping ranges are the primary repeat signal — re-fetching the same lines through a different wrapper is caught, while strictly-disjoint forward paging and different files stay silent. |
| `near_identical_warning_attempts` | `2` | How many times the near-identical notice may be injected *per distinct command family* across the run. Once a family exhausts its budget it escalates into hard repeated-call detection (nudge via `repeated_recovery_attempts`, then fail) instead of going silent — a persisting churn loop can never hide behind a spent global counter. `0` disables the feature entirely. |
| `iteration_warning_margin` | `50` | Iterations before `max_iterations` at which a hard wrap-up notice is injected (stop starting work, hand remaining items + context to parent). Must be `>= 1`. |
| `iteration_warning_attempts` | `1` | How many times the low-iteration wrap-up notice may be injected. `0` disables the feature entirely. |

### Wall-clock & token budget

| Key | Default | Description |
|-----|---------|-------------|
| `timeout_seconds` | `7200.0` | Wall-clock budget for a single agent's *entire* run (whole context), in seconds. After this the loop force-fails with a timeout. `None`/`null` disables the cap; `0` is rejected (must be `> 0` when set). Cost is then bounded only by `max_iterations` / `max_agent_tokens`. Separate from `llm.call_timeout_seconds`. |
| `disable_root_timeout` | `true` | Exempt only the top (root) agent from `timeout_seconds`. The root runs until it finishes on its own; the person supervising decides when to kill it. Children still inherit the cap, so a stuck child force-fails and stays recoverable via `resume`/self-heal. The per-call httpx timeout still bounds every request. |
| `max_agent_tokens` | `null` | Hard cap on total tokens (prompt + completion) a single agent may use before it is force-failed. `None`/`0` disables the cap (the field is `ge=0`; `0` is normalized to `None`). When set, surfaced to the agent each turn as a live token budget; the `usage` tool lets an agent read its own counters. Recommended per-agent guidance: stay under ~50,000 total tokens. The wall-clock handling in `timeout_seconds` is unchanged — it is carried through to the per-agent `TimeoutPolicy` in `core/policies/` (see `docs/api/policies.md`). |

### Delegation / spawn caps

| Key | Default | Description |
|-----|---------|-------------|
| `max_agents` | `300` | Hard cap on total agents per run (root included). Must be `>= 1` (or `null` to disable). Reaching it makes every further `delegate` refused (never creates an agent). |
| `max_depth` | `15` | Hard cap on tree depth (root = 0, its children 1, ...). Must be `>= 1` (or `null` to disable). Delegating past it is refused. |
| `max_same_target_delegations` | `0` | Per-lineage cap on delegations aimed at the **same target** (normalized file/directory path(s) in the description, via `delegate_target_signature`). The counter is shared across an entire family (root → all descendants), so re-spawning the same "explore X / read X" sub-agent — including across self-heal fresh restarts — trips this cap and is refused at the runtime choke point. **`0` or `null` disables the cap** (the field is `ge=0`; `0` is normalized to `None`). |
| `spawn_limit_warning_attempts` | `2` | How many times a non-fatal "you are near the delegation caps" notice may be injected before a cap is hit. Fires once per cap at 80% usage. `0` disables the feature entirely. |

**Interaction with the config disable convention:** `max_agent_tokens` and
`max_same_target_delegations` accept `0` in config and normalize it to `None` (cap off);
`max_agents`, `max_depth`, and `timeout_seconds` require `null` (since they are
constrained `>= 1` / `> 0`). The delegate-tool refusal messaging reads the normalized
fields, so a disabled cap shows no budget line for that cap.

Example:

```json
{
  "safety": {
    "max_iterations": 400,
    "repeated_call_limit": 5,
    "repeated_recovery_attempts": 2,
    "repeated_call_exempt_tools": ["status", "usage", "result_read", "result_bash"],
    "near_identical_threshold": 3,
    "near_identical_window": 6,
    "near_identical_similarity": 0.6,
    "near_identical_tools": ["bash"],
    "near_identical_warning_attempts": 2,
    "iteration_warning_margin": 50,
    "iteration_warning_attempts": 1,
    "timeout_seconds": 7200,
    "disable_root_timeout": true,
    "max_agent_tokens": 50000,
    "max_agents": 300,
    "max_depth": 15,
    "max_same_target_delegations": 0,
    "spawn_limit_warning_attempts": 2
  }
}
```

> **Note:** `max_same_target_delegations: 0` above deliberately disables the same-target
> cap (a developer harness with a tightly-scoped agent that may re-aim at the same path).
> See [disabled caps](#setting-0-vs-none-disable-a-cap).

---

## `self_heal` — failure recovery

Bounded, diagnosis-driven recovery for agent runs that end in failure. See
`docs/concepts/self-healing.md` for the full layered policy.

| Key | Default | Description |
|-----|---------|-------------|
| `mode` | `true` | Master switch for self-healing. `false` disables recovery entirely. |
| `max_resumes` | `1` | Bounds Layer 1: resume the same agent with a corrective nudge (salvages a healthy context). `>= 0`. |
| `max_fresh_retries` | `1` | Bounds Layer 3: spawn a fresh worker over the same task when the context is poisoned / rot. `>= 0`. |

Example:

```json
{
  "self_heal": { "mode": true, "max_resumes": 1, "max_fresh_retries": 1 }
}
```

---

## `agent` — agent behavior

| Key | Default | Description |
|-----|---------|-------------|
| `environment_notes` | `["Working dir is project root; run \`pytest\` from there."]` | Extra environment instructions appended to every agent's context observation (e.g. "pip is unavailable"). |
| `references_dir` | `null` | Directory of durable, git-tracked reference docs (rationale, tool motivations, guidelines) that survive prompt optimization. A compact index is injected into every agent's environment; the agent reads full bodies on demand. Defaults to `docs/references` relative to the working directory. |
| `active_turn_window` | `50` | How many recent committed turns the Context Observation lists. Must be `>= 1`. |
| `stream_children` | `true` | When true, an agent that delegates multiple children stays responsive: it is re-admitted to its LLM loop as each child settles (report/escalate/fail) instead of blocking until ALL children finish. Lets a parent react to child events — re-delegate a failed branch, converse, cancel the rest, or report early — before its siblings are done. Cost: generally more LLM turns per parent. Set `false` to restore block-until-all semantics. |

Example:

```json
{
  "agent": {
    "environment_notes": ["Working dir is project root; run `pytest` from there."],
    "references_dir": "docs/references",
    "active_turn_window": 50,
    "stream_children": true
  }
}
```

---

## Setting `0` vs `null` — disabling a cap

For the cap-facing keys, the runtime normalizes the internal value to `None` when it is
falsy, and the cap is only enforced when the internal value is **not** `None`. Whether
`0` is a valid way to express "disabled" in JSON depends on the field's Pydantic
constraint:

| Key | `0` allowed? | `null` allowed? | Effect |
|-----|------------|----------------|--------|
| `max_agent_tokens` | Yes (`ge=0`) | Yes | `0`/`null` disables |
| `max_same_target_delegations` | Yes (`ge=0`) | Yes | `0`/`null` disables |
| `max_agents` | No (`ge=1`) | Yes | only `null` disables |
| `max_depth` | No (`ge=1`) | Yes | only `null` disables |
| `timeout_seconds` | No (`gt=0`) | Yes | only `null` disables |

So both forms work for `max_agent_tokens` and `max_same_target_delegations`:

```json
{ "safety": { "max_agent_tokens": null } }
{ "safety": { "max_agent_tokens": 0 } }
```

For `max_same_target_delegations`, `0`/`null` means same-target re-delegation is
**never** refused — an agent may re-aim at the same path as often as it likes (bounded
only by `max_agents`, `max_depth`, and the loop caps).

For `max_agents`, `max_depth`, and `timeout_seconds`, use `null`:

```json
{ "safety": { "max_depth": null } }
```

Note that `0` is **not** meaningful for a boolean switch (e.g. `stream_children`) or for
a "how many notices" counter (`near_identical_warning_attempts` = `0` means the feature
is silent, which is a *valid* disabling behavior).