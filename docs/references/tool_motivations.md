# Tool Use-Cases and Motivation

Durable statement of *what each tool is for and why*. The optimized prompt lists tools
and gives terse guidance. When the motivation behind a tool, or when to prefer it over
another, has been optimized away, recover it here via `read`.

## Discovery tools

- **glob** — cheap way to find which files exist in the workspace before reading.
  Always prefer listing a directory with `glob` over guessing paths. A glob that yields
  nothing is a signal the guess was wrong; *ask* rather than fabricate a path.
- **grep** — search file *contents* by pattern, with `include` to filter by extension.
  Use when you need to locate code by symbol/behavior, not when a path is already known.
- **read** — pull a specific known file. Use `token_limit`/`token_offset` to page through
  large files so you never pull an entire file into context. Read summaries, not bodies.

## Workspace tools

- **write** — persist a finding/artifact to disk. Every material result must be written
  before `report()`. Never report without a disk artifact.
- **edit** — surgical in-place replacement (first occurrence only) of the *first* match.
  Use when you know exactly what to change and where; use `write` for whole-file content.
- **bash** — run commands, builds, tests, git. It is a raw command executor, not a shell —
  no pipes/redirects/`&&`. Use it to *verify* (run the test) and to act (create dirs).

## Network

- **webfetch** — retrieve external content. Restricted to safe destinations (no
  localhost/private ranges). For information, prefer it over the network; for multiple
  pages, prefer delegating children to fetch in parallel.

## Coordination & control

- **delegate** — the core tool: split work into a fresh, isolated sub-agent. Always
  prefer delegation once a task needs 2+ tool calls. Delegate everything you can,
  in parallel, in one turn.
- **converse** — push a *specific already-created* child to do more or clarify its
  output. Prefer this over pulling a child's full artifact into your context.
- **status** — read the live status *and* partial progress of your delegated children
  (or one by id). Each snapshot carries the child's outcome (`running`/`completed`/
  `failed`/`killed`/`escalated`), final summary or failure reason, artifact, its plan
  (done + pending steps), and `partial_data` — a bounded tail of recent in-context
  activity. Consult it after any child fails or lingers to see what already succeeded.
- **kill** — cancel a stuck/looping/rogue child (optionally its whole subtree via
  `recursive`), preserving what it already wrote. The kill result embeds `salvage`: a
  per-agent snapshot of the killed work, so you immediately see the partial data it
  produced before it died — the raw material for a targeted retry rather than a
  from-scratch restart. Killed agents are excluded from self-heal (never resurrected).
- **read_artifact** — read a stored artifact by ID across the progressive-disclosure
  view (headline → summary → technical). Verify children by summary first.
- **usage** — read your own cumulative message/token counters and live-context
  estimate. The cache-friendly way to self-monitor: consult it when work grows
  repetitive (before delegating/pruning/compressing) instead of waiting for a
  per-turn observation that would zero the provider prompt cache.

## Context-management tools

- **compress** — summarize the conversation to reset context when it grows past ~50
  messages. Aggressive, lossy; prefer `prune` for dropping discrete stale turns.
- **prune** — drop specific stale committed turns (results already on disk) to keep
  context bounded while preserving recoverability via `restore`.
- **restore** — recover a pruned turn's full content on demand.

## Termination tools

- **report** — terminal; submit verified results with concrete summary + artifact_ids.
- **escalate** — terminal; a structural/design blocker on the child's scope, raised to
  the parent. The parent owns the child's outcome.
- **fail** — terminal; unrecoverable error. Everything failed *must* be retried or
  escalated; never silently abandon a failed child.
- **kill** — a *parent-side* abrupt stop of a child (see "Choosing between similar
  tools"). Not a child terminating itself; it lets the parent abort stragglers and
  recover their partial work for a retry.

## Choosing between similar tools

- **grep vs read**: grep to *find*; read to *consume*.
- **glob vs grep**: glob to *enumerate*; grep to *search contents*.
- **edit vs write**: edit for a targeted change; write for fresh/whole content.
- **delegate vs do-it-yourself**: 0–1 calls on a known target → do it; anything
  non-trivial (2+ calls, chained discovery, unknown scope) → delegate. Under-delegation
  is a failure mode. Over-delegation is never a flaw.
- **verify vs trust**: never synthesize from the *return summary* alone; verify the
  artifact on disk. The summary is a preview; the artifact is the truth.
- **converse vs re-delegate**: converse pushes the *same* agent forward; re-delegate
  spawns a *fresh* worker. Prefer `converse` when the child is healthy and just needs
  more direction; prefer `kill` + re-delegate when the child is stuck, poisoned, or
  structurally unable to finish.
- **status vs read_artifact**: status tells you *how* a child's run went (status,
  failure, done/pending plan, salvaged progress); read_artifact reads the *content* it
  produced. Use status to decide *whether/how* to retry; use read_artifact to consume
  what it succeeded in writing.
