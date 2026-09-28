# Self-improving context management

## The question

Should the agent be enabled to improve upon its own tools and context management —
memory, summaries, compression, or similar — and how does that stay compatible
with the commit structure that keeps each level of context small?

## Answer: yes, in tiers

| Tier | What it means here | Verdict |
|---|---|---|
| 1. New capabilities as procedural skills | A validated routine is persisted as a skill (`type: procedural`) | **Yes — already in [proposal.md](proposal.md) §3.** Additive, plain-text, reviewable; no invariant touched |
| 2. Authoring its own context management | The agent writes its own summarizer / prune strategy / compress cadence / memory format, *used within its own loop* | **Yes — bounded by the contract, chosen by measurement** (below) |
| 3. Altering runtime machinery | Editing config, policies, summarization thresholds, repository/commit semantics, safety knobs | **No — that is the decision-log's job.** An agent that owns its own safety/commit machinery stops being an actor in the harness and becomes the harness; unbounded self-modification is where the system stops being auditable |

Tier 2 is the interesting case. The harness *already* delegates per-agent context
management to the agent — `compress`, `prune`/`restore`, `usage` are deliberate
"self-regulate" tools (`core/tools/context.py`) — but they are fixed-function
today: the agent can *use* them, never *change* their behavior. Enabling
improvement means letting the agent author its own routines and **compete them
against the defaults on the same measured metrics** — the same delta-discipline
this investigation applies everywhere ([proposal.md](proposal.md) §5).

## The discipline: improve the *production* of small layers, never the *contract* that enforces smallness

These contracts stay runtime-owned no matter what the agent writes:

- `deliver_report()` creates the Commit; `ArtifactStore` writes immutable,
  level-bounded views (`memory/repository.py`, `artifact/store.py`). The agent
  never writes to these paths.
- State lives in artifacts, not agent memory (principles #5/#6). A
  memory-format "improvement" is only an improvement if it is *itself an
  artifact* — bounded, consumable, summarizable — never an opaque private blob
  the runtime cannot see.
- The commit structure is the **incentive**, not just storage: committed
  artifacts are consumable by parents (that is where an agent's work becomes
  visible and credit-earning), while hoarded context is invisible. The commit
  path therefore remains the only route to influence — architecture keeps the
  reward on committing small, not hope.

## How "keep each level small" stays encouraged — structural, not aspirational

1. **Enforce level budgets at the runtime.** The disclosure levels (headline →
   200-char → 1000-char → technical → full) get size budgets enforced where
   artifacts are written — an "improved summarizer" whose outputs breach the
   level budget is rejected/truncated by the runtime, not by the agent's taste.
   Improvement cannot mean "bigger layers".
2. **Measure and feed back.** Per-commit token footprint, per-level sizes, and
   `compress`/`prune` efficacy are harvested from the existing telemetry/trace,
   so a proposed context-management improvement is adopted or refused on
   evidence of whether it actually kept layers small, not on the agent's
   argument.
3. **Admit improvements through the same validation gate as skills.** A new
   summarizer/pruner is a `type: context-management` skill; it survives only if
   the benchmark context-efficiency score (solve task at ≤ turns / tokens /
   level-size) improves — the CodeMem/AgentFactory "survivors only" selection,
   wired to the [proposal.md](proposal.md) §5 gate.
4. **Pair smallness with verification.** Smallness-as-hiding is the real hazard
   (a worker's self-written summary can drift toward "looks done"). The existing
   pairing — immutable commits + parents verify-before-synthesize + `restore` /
   checkpoint markers — is what keeps "small" from sliding into "lossy".
   Enforced level budgets (1) close the loop: small *and* verified, or rejected.

Net effect: agents can improve how they **generate** small layers (better
summaries, pruning, memory formats), while the runtime keeps the commit graph and
level structure as the enforced, measured, rewarded skeleton — the capability
*reinforces* commit-small instead of eroding it. Every attempted improvement is
observable in telemetry and gated by the benchmark-delta method.

## Related

- [proposal.md](proposal.md) — hybrid design; §3 procedural skills, §5 decision gate
- [worker-formation-option-load.md](worker-formation-option-load.md) — option
  load from cheap capability; rails/tiering/economics
- [benefits-and-costs.md](benefits-and-costs.md) — B7 self-evolution evidence
- [INVESTIGATION.md](INVESTIGATION.md) — canonical record