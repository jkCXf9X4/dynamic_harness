---
title: "Competitive Differentiation"
category: meta
summary: >
  What separates Dynamic Harness from other agent harnesses (CrewAI,
  LangGraph, AutoGen, OpenAI Agents SDK, Claude Code, MCP-based tools).
  Distinguishes mechanically-enforced guarantees from prompt-level advice
  shared with the field.
related:
  - ../VISION.md
  - concepts/self-healing.md
  - concepts/agent-lifecycle.md
  - concepts/delegation-model.md
  - ../gap-analysis.md
---

# Competitive Differentiation

This document is a grounded comparison of Dynamic Harness against the
mainstream agent harnesses. It deliberately separates two things:

1. **Mechanically enforced guarantees** — behavior enforced by deterministic
   runtime code, not prompt text.
2. **Prompt-level advice** — shared with the field; documented as guidance but
   not a differentiator.

The framing throughout is: *"If the model disobeys the prompt, what breaks?"*
Dynamic Harness' genuinely distinct claims are the mechanisms that survive
model disobedience.

## Ground Truth: How This Harness Differs by Design

The project's founding thesis is **"fresh context is cheaper than accumulated
context"** (`VISION.md`). A 3-turn sub-agent with a clean slate outperforms a
20-turn monolithic agent at lower cost. Most harnesses share surface features —
recursive delegation, tool-calling loops, context management — but not the
deterministic enforcement described below.

## Mechanically Enforced — Genuinely Distinctive

### 1. Safety as deterministic machinery, not prompt discipline

Mainstream harnesses *tell* the model to behave: "verify your children",
"prune your context", "don't loop". Measured behavior shows the model rarely
complies (it almost never calls `prune` in the manyfiles task, and token use
balloons to 200–680K — `self-healing.md:42-50`).

Dynamic Harness enforces safety in `_run_loop()`:

- **Repeated-call detection** — N identical tool-call batches in a row force
  a fail. Pure monitoring tools (`status`, `usage`, `result_read`, `result_bash`) are exempt
  entirely — a parent polling its self-healing children is waiting, not looping,
  and a turn composed solely of them is not counted at all.
- **Near-identical call warning** — a fuzzy detector that pagination-normalizes
  `bash` signatures (`sed -n 'A,Bp'` / `awk NR>=A&&NR<=B` / `head -N` collapse
  to a family), treats *same-file overlapping ranges* as the primary repeat
  signal, and warns per-command-family with a warning budget
  (`near_identical_warning_attempts`) before escalating into hard repeated-call
  detection. Strictly-disjoint forward paging and different files stay silent.
- The budget is **per command family**, not global — a family that keeps
  re-reading the same material past its budget escalates instead of going
  silent.

Fuzzy near-duplicate tool-call detection at runtime is not present in the other
harnesses surveyed.

### 2. Result caching behind opaque handles (`result_read` / `result_bash`)

Every cacheable tool call (`read`, `glob`, `grep`, `bash`, `webfetch`,
`read_artifact`, `status`, `usage`, …) stores its **full** output in a
per-agent, bounded, in-memory `ResultStore` behind an opaque handle. When a
result is truncated, the footer advertises the handle and the read-only
`result_read` tool pages the snapshot by `result_id` — **never re-executing**
the producing tool. Paging a slow bash/webfetch result is therefore free.
`result_bash` goes further: it pipes the snapshot text to any shell command's
stdin (`rg`, `jq`, `awk`, `wc -l`, `python3 -c '...'`), so the full bash
vocabulary can probe an expensive saved output without re-running the work.

Two properties follow:

- **Handles are always read-only.** Getting a fresh result means calling the
  work tool again (work tools accept no `result_id` input). This is enforced in
  the registry's mutator-set logic.
- **Memory-only, cleared on GC/reset.** A resumed agent never sees stale
  snapshots; an unknown handle errors with "re-run the producing tool".

This is a distinctive cost/context optimization (`core/result_store.py`).

### 3. Blunt-vs-rot self-healing with a shared heal budget

Recovery is diagnosis-driven, not a blanket "always retry":

- **Blunt** (healthy context, single clearable error, prose answer, forgot the
  artifact) → **resume the same agent** with a focused nudge (Layer 1).
- **Rot** (repeated calls, max iterations, wall-clock timeout, repeated Layer-1
  misses) → **spawn a fresh worker** over the same task, injecting the failure
  reason and pointing at the dead worker's on-disk artifacts (Layer 3).
- **Structural** (impossible task, bad spec, willing non-compliance) →
  **escalate** (Layer 4). Never grind.

Two enforcement details distinguish this from prompt-level retry guidance:

- **Shared budget.** Parent-driven `resume` and runtime-driven self-heal consume
  the *same* per-child budget (`max_resumes` / `max_fresh_retries`), so retries
  cannot stack. The `resume` tool lets a parent force `"resume"` (refused on a
  rotted context — replaying poison repeats the failure) or `"fresh"`.
- **The deliverable gate.** A child that completes *in prose* — no artifact, no
  `files_written` — is treated as a failure and healed, at both the root and
  the delegate boundary (`_has_deliverable`). This catches the most common
  silent failure mode.

### 4. Spawn limits at a single choke point, with target signatures

Every spawn — roots, children, self-heal fresh restarts — passes through
`Runtime.delegate()`. Beyond `max_agents` and `max_depth`, there is a
per-lineage `max_same_target_delegations` cap keyed on a **normalized
file/directory signature** extracted from the task description
(`delegate_target_signature` in `core/spawn_limits.py`). Re-spawning "explore
the same repo" over and over — even across self-heal restarts — trips the cap.

Refusals raise `DelegationLimit`; the `delegate` tool surfaces them as a
`status: refused` tool result with a `[delegation budget]` line plus a
`safety_warning` activity. Every delegate result carries that budget line so
the model can self-regulate. When a cap refuses a fresh-worker spawn, the
runtime emits `fresh_refused` and leaves the failed agent in place — bounded
out rather than spawning an agent that should never exist.

### 5. Checkpoint persistence + resumability as first-class

The run loop auto-persists a structured `AgentCheckpoint` after **every**
committed turn. `Runtime.resume(agent_id)` rebuilds a live agent from disk —
across process restarts — and the CLI exposes `/resume`. Combined with the
immutable artifact + commit graph, a crashed or interrupted run is
reconstructable, not restarted.

## Prompt-Level — Shared with the Field

Design intent that is real *in this codebase* but not a mechanical guarantee,
and therefore equivalent to what other harnesses offer at the API level:

| Feature | Status in Dynamic Harness | Disposition vs. field |
|---|---|---|
| Role-scoped tool allow-lists | Enforced in code (`tools/registry.py`) — orchestrators can't do hands-on work | Stronger than most, but "roles" as a concept exists elsewhere |
| Prune / restore / compress context tools | Implemented (`core/context.py`) | Standard context-management surface |
| Progressive disclosure (headline → raw) | Implemented (`artifact/store.py`) | Unusual degree, but the idea exists in artifact layers everywhere |
| Git-like provenance (commits, parents, children) | Implemented (`memory/repository.py`) | Shared with versioned-artifact systems |
| Streaming children (fire-and-forget, event-driven parent reactions) | Implemented (`agent.stream_children`) | Deviates from the default gather pattern — see below |
| Unix-composability (CLI files, not dashboards) | Implemented (`cli/`) | Design choice, not a capability gap |

### Streaming children — a divergence, not a default

By default delegation is all-or-nothing: a parent that delegates several
children blocks until *every* child settles. With `agent.stream_children: true`
children are fire-and-forget and the parent is re-admitted to its loop as each
child settles (`[child settled]` injected), letting it react to one child before
siblings finish — re-delegate a failed branch, cancel stragglers, or report
early. This is an operating-mode choice; the cost trade-off is documented
(`delegation-model.md:20-33`).

## Honest Open Gaps

The `gap-analysis.md` flags two pillars where enforcement is *not yet*
mechanized — these are the weakest differentiation claims today:

- **G1 — Verification is prompt discipline, not a mechanism.** `plan` records
  acceptance criteria, but nothing mechanically evaluates them; "done" is what
  `report()` declares. The "verify before synthesize" guarantee is the least
  enforced pillar and the least differentiated from the field.
- **G8 — Budgeting/cost-control is dead plumbing.** `request_more_budget` and
  `on_budget_request` exist but no tool exposes them and there is no spend cap.
  The "#1 motivation" (cost) is not yet enforceable.

## Summary

| Claim | Mechanically enforced? | Distinctive vs. field? |
|---|:---:|:---:|
| Near-identical bash/loop detection with fuzzy signatures | Yes | **Yes** |
| Result caching behind opaque read-only handles | Yes | **Yes** |
| Blunt-vs-rot self-healing, shared heal budget | Yes | **Yes** |
| Same-target spawn caps (per-lineage) | Yes | **Yes** |
| Deliverable gate heals prose-completions | Yes | **Yes** |
| Checkpoint resume across restarts | Yes | Yes (closer to standard) |
| Verify-before-synthesize | **No (G1)** | No |
| Cost enforcement / budget | **No (G8)** | No |

The defensible "only-us" positioning: **fuzzy repeated-call safety, opaque
result handles, deterministic blunt-vs-rot recovery with a shared budget, and
same-target spawn limits** — mechanisms that keep working when the model stops
following the prompt.