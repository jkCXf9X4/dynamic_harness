---
id: INFO-143
type: info
title: Build vs extend — is this a development of the product, or a new project?
summary: The code-as-action paradigm (single tool; the agent sets up and manages tools, worker groups, memory, and communication from Python) presents complex—…
date: 2026-09-28
status: current
pb_exempt: true
---

# Build vs extend — is this a development of the product, or a new project?

## The question

The code-as-action paradigm (single `invoke(code)` tool; the agent sets up and
manages tools, worker groups, memory, and communication from Python) presents
complex—collaborative development. Is adopting it a **development of this
product** (dynamic_harness) or a **new project** that should be aligned from the
start under its own identity?

## The intent layer settles the framing

`00-intent/VISION.md` draws explicit boundaries, and one line is decisive:

> **Not a code generation platform** — agents use tool calls, not generated code.
> (VISION.md:59)

That line is the product's identity, and it is precisely what `invoke(code)`
inverts. Mapping the paradigm against the nine core principles:

| VISION principle | Code-as-action impact | Verdict |
|---|---|---|
| "Agents use tool calls, not generated code" (:59) | One tool whose action *is* generated code | **Direct contradiction** |
| Fresh-context economics, 3×3-turn > 20-turn monolith (:10–13, :44) | Long-horizon single-agent sessions are the paradigm's economics | Tension — rescued only by the delegate caps + worker formation |
| Context encapsulation, runtime-owned graph (:38) | Agents set up own worker groups / choose comms topology | Tension — caps hold the gate; orchestration style moves to the agent |
| Disposable workers, state in artifacts (:46) | Agent-authored memory / context management | **Compatible** — bounded by the tier-2 contract in `INFO-145` |
| Artifact-driven, progressive disclosure, ~300 not 30,000 tokens (:40–43) | Only `print()` enters context | **Reinforces** (B1/B4) |
| Compulsory verify-before-synthesize (:29) | Execution feedback grounds verification | Helps, no conflict |

Everything *around* the core aligns; the paradigm's *defining trait* is the one
thing the product explicitly disclaims.

## Verdict: development as a mode; new project as the end-state

**1. The hybrid capability is a development.** An `invoke` tool + `harness_tools`
stub + procedural-skills pipeline (`INFO-146`) is additive: it
extends the surface, keeps every invariant (spawn caps, artifact/commit path,
terminal contracts, loop guards), and is framed as an *optional agent type*, not
a rebranding. `bash` is already a do-anything tool — `invoke` is the same
category. Nothing forces VISION to change.

**2. The single-tool, paradigm-first end-state is a new project.** A
code-as-action runtime is a different product (OpenHands/Manus/Codex-shaped):
different action discipline (structured tool surface → one executable action
space), different economics (fresh-context decomposition → long-horizon sessions
with full compute in a VM sandbox), different trust model (host + policies →
per-task sandbox VM), and it fails VISION's own "not a code generation platform"
boundary. Retrofit is a lose-lose — the product stops being itself, or the
paradigm is throttled into not being itself.

**Signal in the evidence:** this investigation has consistently produced
*restraint* rules (three lab rules, three tiers, "settled decisions stay
settled", "measure before committing"). That recurring friction is the signature
of identity mismatch — the VISION-compatible constraint fights the paradigm's
natural shape. A greenfield would not need it.

**3. The low-cost fork.** The "new project" is **not from-zero**: the shared
skeleton is large and stable — event bus, task-graph orchestration,
`ArtifactStore`, `Repository`/commits, telemetry/trace, checkpointing, policies,
comms layer, benchmark suite. The real fork is *new product on the shared
skeleton* with a rewritten `00-intent` and a different action discipline. Low
fork cost is exactly why honest segregation beats graft: picking "new project"
if evidence says so costs little, and it avoids dragging 34-tool schema baggage
and bash-shaped guards into a paradigm they oppose.

## Recommended sequence (evidence-first)

1. **Develop the probe inside this product** — the hybrid (`invoke` + stub +
   `codeact` agent type on the benchmark suite). This harness is the cheapest
   place to produce the deciding numbers because the equipment (bench,
   telemetry, per-model runs) already exists.
2. **Judge it by this product's own success criteria** (VISION.md:69–75):
   verified output, no fabrication, shallow total context, cost ∝ complexity,
   no abandoned children. The identity question becomes numeric: does
   single-tool code-first beat *this* product on *its own* criteria?
3. **Route the answer by rule, not retrofit.** No-but → the hybrid stays a
   feature; the paradigm is recorded as explored-and-rejected in the decision
   log. Yes-but-with-structure → found it as **its own product on the shared
   skeleton** (new `00-intent`); do not graft.
4. **Keep the intent explicit.** Either VISION:59 stays and governs
   (recommended until evidence flips it), or — only if the intent genuinely
   shifts — amend it via a decision-log record. No implicit contradiction: until
   then the `codeact` agent type remains an *experiment type*, never the
   default. Existing assets (`INFO-142`,
   `INFO-144`,
   `INFO-147`,
   `INFO-145`) stay
   as the evidence record either way.

## Bottom line

Reasonably a development? **The capability: yes. The paradigm-as-product: no.**
The correct shape is both, sequenced — develop the probe here, and be willing to
found it elsewhere on the shared skeleton if the measurement says so.

## Related

- `INFO-001` — the identity this evaluation is grounded in
- `INFO-146` — the hybrid prototype this sequences with
- `INFO-141` — the canonical record
