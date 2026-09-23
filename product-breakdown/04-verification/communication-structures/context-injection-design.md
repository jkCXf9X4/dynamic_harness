---
title: "Analysis — Injecting Communication into Agent Context"
category: investigation / analysis
status: open
summary: >
  How communication enters an agent's context: inject typed envelopes, not raw
  content; tail-appended user messages keep the prompt prefix cache-safe; a typed
  envelope frames channel traffic as related work, not instructions.
parent: "INVESTIGATION.md"
---

# Injecting communication into agent context

Injection mechanics only. Channel pollution containment, directory, and creation
rules are in [channel-context-design.md](channel-context-design.md); the concrete
tool surface is the plan ([PLAN](plan/README.md)).

## 1. Inject envelopes, not content

Three existing precedents generalize:

- **Tail-append user role only.** `PromptInjection` is applied as a fresh user
  message (`core/policies/interface.py:36` — "tail-append-only, so the cached
  prompt prefix stays contiguous"); every injection (`[child settled]`, notices,
  user input) follows this. Mid-prefix insertion is off the table.
- **The `[child settled]` precedent** (`core/agent.py:975 _format_delegate_result`)
  injects a **folded JSON envelope** (`child_id, status, summary ≤2000 chars,
  artifact_ids, confidence, failure`) — never the child's context; content stays
  on disk, pulled via `read_artifact`/`result_read`.
- **Index-not-body precedent** (`core/references.py:82 render_reference_index`):
  tell the agent the library *exists and where*; pull bodies on demand.

Decision rule (media-richness stance):

| Exchange | Injection |
|----------|-----------|
| Lean / factual (finding, file, constraint) | Pointer-only envelope; agent pulls |
| Equivocal (negotiation, "why is this wrong?") | Summary envelope + pointer, bounded; full thread stays out |
| Never | Raw channel content, full sibling context, message history |

A push is **not free**: every injected token is re-sent on every subsequent LLM
call (cost multiplier = remaining turns) — the budget justifying envelopes.

## 2. "Related work, might need to take into account" — relevance framing

The agent won't *miss* injected content; the failures are treating an irrelevant
post as an instruction and paying the multiplier for irrelevant tokens. Fix both
with a **typed envelope** (concrete renderer: [plan/injection.md](plan/injection.md)):

- **`kind` is load-bearing.** `instruction` (parent/context — binding) vs
  `notification` (channel — advisory, ignorable); the envelope *names* the
  authority, so the model never guesses.
- **Metadata for self-scoring relevance:** `topic`, `sender`, `stage`
  (draft/revised/final), recency — cheap to score, zero reading.
- **Progressively disclose** headline → summary_200 → technical → full via a
  pointer (the `ArtifactView` ladder).
- **Cap the digest per turn** (N newest / M tokens, newest-first): triage over a
  bounded surface. Add **push-multiplier** (avg tokens × turns remaining) to the
  success battery.
