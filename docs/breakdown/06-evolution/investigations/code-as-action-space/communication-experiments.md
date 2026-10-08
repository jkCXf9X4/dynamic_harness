---
id: INFO-144
type: info
title: Communication experiments via code-as-action
summary: "Communication is the dimension where the design space is largest relative to what is built: four fixed topologies ( / / / ) against several still-open…"
date: 2026-09-28
status: current
---

# Communication experiments via code-as-action

## Why communication is the highest-leverage probe surface

Communication is the dimension where the design space is largest relative to what
is built: four fixed topologies (`relay` / `siblings` / `shared` / `topics`)
against several still-open questions (cadence, equivocality, introduce,
authority). With `invoke(code)`, a communication **variant** becomes a Python
module over the shared workspace — the message store, addressing, and
consumption policy are *code*, not new backend classes, policies, config, and
tests. The variant is then expressible in ~tens of lines and runnable per
experiment.

The harness already has the lab equipment:

- `benchmark/` suite with deterministic scoring (`benchmark/tasks.py`,
  `benchmark/scoring.py`) — task success is measured, not eyeballed.
- `comms.jsonl` trace — the cross-agent audit, `tail -f`-able.
- `CommsDigestPolicy` caps + ResultStore / `result_read` handles — traffic can be
  *sunk out of context*, so the context cost of a variant becomes directly
  attributable instead of confounded.

And context/token economics is the stated #1 motivation while comms traffic is
the churn variable (IMP-001) — code-as-action turns that variable into a tunable
of the experiment.

## What a "variant" is (enabler form)

A variant = **(message store format) × (addressing/visibility) × (consumption
policy)**, expressed as a Python module the agent runs via `invoke`, over the
shared workspace. Only the printed summary enters context; everything else lives
in sandbox files / ResultStore handles.

## Variant matrix

| Open question (existing) | What is probed | Variants code-as-action makes cheap |
|---|---|---|
| IMP-002 round/cadence semantics | When a child fetches newly-settled siblings' writes | Poll-before-report · mtime-watermark fetch · manifest + fetch-only-new · bounded-redo. Measure context cost vs freshness |
| IMP-003 equivocality (write vs message) | How ambiguity arises between siblings | Storage protocols: append-only JSONL per-agent mailbox · shared board with row ownership · sqlite inbox (`SELECT` unread) · directory-per-topic · git-commit-per-message (free provenance). Measure re-requests |
| IMP-004 introduce mechanism | Delegation-time vs mid-run introduction | Parent writes a "here are the others" ledger entry by code; read patterns measured without a tool change |
| ChannelPolicy authority | Who may create/join topics | Visibility variants: open board vs private inbox vs role-scoped — per-experiment, before committing policy |
| Digest/consumption caps (`CommsDigestPolicy`) | How much traffic enters each agent's context | Harness digest (baseline) vs code-side summarization (print 3 lines from N) vs no-consumption (files only) |
| Backend topology futures | Properties of a hypothetical backend | Emulate a candidate backend (broadcast-with-dedup, post-office-with-delay) as code to measure properties before building the class |

## The three lab rules (guarantees vs freedom)

The existing comms layer's value is guarantees — cross-agent trace, watermark
deltas, digest caps, authority checks. Code-side communication has none of those
by default. Three rules keep it an honest lab:

1. **Trace-stamped** — every variant carries a variant id + event log, *even when
   routing is off-harness*; preserve the "one file, readable with `tail -f`"
   property of `comms.jsonl` per variant. Without this the experiment is
   unreadable and non-reproducible.
2. **Tool-comms stays the control** — the baseline is the current backend +
   digest caps on the same task matrix, so the sweep measures the actual delta
   of each variant, not the absence of a baseline.
3. **Settled decisions stay settled until evidence flips them** — this is a probe
   surface for IMP-002/003/004 and topology futures, *not* a re-litigation of
   the DL-* / channel decisions (workspace-primary, messages-as-exception),
   introduce-not-mediate, or the L0/L1/L2 facilitation layer. A winning variant
   gets spec'd as real mechanism through the RPC stub (`INFO-146`)
   — the stub is both the enabler (code reaches `post` / `channel_read` /
   `converse`) and the boundary (actor isolation re-imposed on demand).

## Concrete minimal experiment

4 storage variants (mailbox JSONL / sqlite inbox / topic board / whiteboard) ×
1 matrix task (5 children, independent work + converge), `codeact` agent type vs
default agent. Scored on: task success (deterministic scoring), turns, tokens,
per-agent context growth, measured equivocality (agents re-requesting
already-written info), and churn in the variant trace vs baseline.

## Related

- `INFO-146` — the hybrid (`invoke` + `harness_tools` RPC stub +
  procedural skills); policy parity by construction
- `INFO-141` — the canonical record
- Multi-agent coordination leaves: channel-decision (`product-breakdown/06-evolution/multi-agent-coordination/channel-decision.md`),
  channel-evidence (`product-breakdown/06-evolution/multi-agent-coordination/channel-evidence.md`),
  introduce-not-mediate (`product-breakdown/06-evolution/multi-agent-coordination/introduce-not-mediate.md`),
  facilitation-layer (`product-breakdown/06-evolution/multi-agent-coordination/facilitation-layer.md`)
- IMP-001..004 — roadmap (`INFO-196`)
- Communication structures plan (`04-verification/communication-structures/plan/README.md`)