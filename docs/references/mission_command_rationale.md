---
name: mission-command
description: Why parent agents brief children with intent, end state, constraints, and freedom of action (uppdragstaktik / mission command). Read when a brief's why has been optimized away from the prompt.
roles:
  - orchestrator
---

# Rationale: Mission Command (Uppdragstaktik) for Delegation Briefs

Durable statement of *why* parent agents should brief delegated children the way
they do, drawn from the Swedish Försvarsmakten leadership philosophy
**uppdragstaktik** (the Swedish term for *mission command*, German
*Auftragstaktik*). If the intent, end-state, or constraint guidance has been
optimized out of the live system prompt, recover the full reasoning here via
`read`.

## What mission command is

Uppdragstaktik is a **decentralized leadership philosophy**, not a command
structure. The Försvarsmakten describes it as: *ledning och beslut
decentraliseras så långt ut i organisationen som möjligt* — command and
decision-making are pushed as far down as the situation allows. It emerged in
the 19th-century Prussian army (after Jena, via Scharnhorst and Moltke) as the
answer to a fundamental problem: **no plan survives contact with the
situation.** When the conditions change mid-execution, the unit that must wait
for new orders is lost; the unit that can decide for itself survives.

The doctrine is simple in shape and hard in practice:

1. The superior states **what** must be achieved and **why** — the mission, the
   objective, and the intent.
2. The superior states the necessary **constraints** — resources, rules of
   engagement, limits, deadlines.
3. The **how is left to the subordinate** — full freedom of action within the
   intent.
4. The subordinate has the **mandate to decide on its own** when the situation
   changes, even if that deviates from the original plan.
5. The precondition for all of this is that the subordinate **understands the
   superior's intent** — because the intent, not the plan, is the anchor for
   correct autonomous decisions.

Swedish doctrine separates the *philosophy* (uppdragstaktik) from the *content
that makes it work*: **målbild** (the picture of the desired end state),
**syfte/avsikt** (the purpose), and **genomförandeidé** (the concept of how the
whole operation is intended to unfold). Together these let a subordinate answer
*"the original plan is now infeasible — what do I do instead?"* without calling
home.

## The commander's intent structure

Across NATO doctrine (US FM 6-0, UK JDP, Bundeswehr ZDv 10/1) the intent is
built from a few fixed elements. Each has a direct analog in a delegation brief:

| Element | Doctrine meaning | Why the subordinate needs it |
|---|---|---|
| **Uppgift** — mission | What must be accomplished | Gives the task itself |
| **Syfte** — purpose | Why this task exists in the larger effort | The decision criterion: when in doubt, choose the action that serves the purpose |
| **Målbild** — end state | The desired final condition ("what done looks like") | The target the subordinate steers toward when the path changes |
| **Genomförandeidé** — concept | How the whole effort is intended to unfold, so parts act in concert | Lets the subordinate keep its execution *compatible* with siblings |
| **Ramar** — constraints/restraints | Resources, handlingsregler (rules of engagement), boundaries, limits | Defines the legal/safe space the subordinate may operate in |
| **Handlingsfrihet** — freedom of action | The how is deliberately not prescribed | The explicit license to exercise judgment instead of asking |

The inverse — dictating both *what* and *how* in detail — is the failure mode
called *kommandotaktik* (directive/instructional control): it robs the
subordinate of initiative and makes the whole tree brittle to friction.

US doctrine (FM 6-0) states the operating principles behind this: *create
shared understanding, provide a clear commander's intent, exercise disciplined
initiative, use mission orders, accept prudent risk* — all resting on *mutual
trust*.

## Mapping to Dynamic Harness today

The parent → child brief is currently built from the `delegate` tool's
`description` + `role` (+ optional `system_prompt`, `agent_type`, `metadata`).
The system prompt's BRIEF line compresses this to: *"description+role; specific
paths/functions/behavior; outcome not process; verification; disk artifact;
acceptance criteria; one task per delegation."*

| Doctrine element | Current analog | Status |
|---|---|---|
| Uppgift (mission) | `description` | Present |
| Syfte (purpose) | Only implicit inside `description` | **Missing as a structure** |
| Målbild (end state) | "Acceptance criteria" — prose advice in the BRIEF rule | Advice only, not a first-class field |
| Genomförandeidé (concept) | Nothing | Missing |
| Ramar (constraints) | `role` (soft scope); `delegate` result / `status` now surface the child's runtime limits (token cap / wall-clock); hard enforcement remains in the safety system | Communicated to the parent; the child's own brief still lists them only if the parent writes them |
| Handlingsfrihet (freedom of action) | "Outcome not process" in the BRIEF rule | Implicit only — no explicit mandate to adapt |
| Authority to deviate | `escalate`/`fail` exist, but deviation is not framed as authorized | Missing |
| Trust → verify | "Never synthesize from assumed results"; verify by artifact | Tension with doctrine (below) |

## The gap: intent is withheld for encapsulation's sake

The framework's architecture deliberately gives a child **only** its
description + role — *"nothing from your parent"*. That encapsulation is what
keeps contexts shallow and cheap. But mission command says a mission without
intent is exactly the case where a subordinate **cannot** make correct
autonomous decisions:

- The child's plan hits friction → it has no end state to steer toward, so its
  options are: grind on the dead plan, fail, or escalate.
- A failed child is then recovered by the parent's kill → retry loop — the
  *most expensive* outcome, and precisely the one an intent block exists to
  prevent.
- The runtime's safety caps (spawn limits, budgets, timeouts) act as
  *handlingsregler* but are **discovered by being hit**, not communicated up
  front — so children cannot self-regulate against them.

The intent is therefore not context *noise*; it is the **decision criterion**
that makes delegated autonomy safe and aligned. It is the same economics as
fresh-context theory: a few hundred tokens of intent up front buys insurance
against a failed child's full context + retry cost. Encapsulation should
protect the parent's context from the child — not deprive the child of the
parent's direction.

## Design implications

Implemented status is noted per item (see `core/task.py`, `core/prompts.py`,
`core/tools/agents.py` for the live wiring).

1. **Structured intent block.** Give the `delegate` tool (and `Task`) a compact
   intent carrier — purpose, end state, constraints, and the license to adapt —
   rendered into the child's context. Keep it to a few sentences; a
   verbose intent becomes *kommandotaktik* by another name and defeats the
   fresh-context economy. **[implemented]** `Task` carries
   `intent`/`end_state`/`constraints`/`authority`; `delegate`'s
   `intent`/`end_state`/`constraints`/`authority` fields render as
   `[INTENT]` / `[END STATE]` / `[CONSTRAINTS]` / `[AUTHORITY]` blocks baked
   into the child's **system prompt steerage** (`Agent._build_steerage`) — the
   compression-surviving, cache-friendly layer, since `context.compress` keeps
   only the system message and erases the user message.
2. **Acceptance as contract, not advice.** "Done looks like X" should be a
   stated field the child verifies against and the parent re-verifies against —
   mirroring the `plan` tool's `acceptance` parameter. **[covered by**
   `end_state`**]** — the parent states the desired final condition explicitly,
   and the child steers toward it when the path changes.
3. **Mandate to adapt + report back.** State explicitly: *if the situation
   changes, deviate as needed to honor the intent; report the deviation and why
   in your report/escalate.* This turns the child's two bad exits (plow ahead /
   fail) into a third, aligned one. **[implemented]** — the `authority` field.
4. **Communicate the ramar up front.** The child's own hard limits (token
   budget, timeouts, delegation caps) should be surfaced as constraints in the
   brief, not as surprises the safety system reveals on violation.
   **[implemented]** — the `delegate` result and `status` snapshot carry the
   child's `limits` (token cap / wall-clock) for the parent; and the child's own
   system-prompt steerage now states its wall-clock budget (`_build_steerage`)
   alongside the existing `[Budget]` token-cap block, so both sides see the
   real ramar up front.
5. **Verify against intent, not plan-adherence.** The parent's VERIFY step
   checks the artifact "matches the requirement"; the requirement should be the
   *end state*, not whether the child followed the original plan.
   **[implemented]** — prompt-level guidance (see the VERIFY rule): non-empty +
   satisfies the `end_state` you briefed.
6. **Observe brief completeness, don't just hope for it.** Prompt guidance
   alone lets a parent delegate WHAT without WHY. **[implemented]** —
   `core/policies/brief.py` (`BriefPolicy`) is a `ReactivePolicy` registered on
   every agent (default `safety.brief_nudge_attempts: 1`): it watches
   `delegate` calls in the post-turn observation and injects a budgeted notice
   naming the missing `intent`/`end_state` dimension(s). Host-agnostic — a
   plugin host can register/replace/rephrase it through the reactive-policy
   seam without touching the run loop.

The discipline stays "minimal **and complete**": the brief must contain the
mission, the intent, the constraints, and the acceptance — and nothing else.
That is the same rule as the current guidelines, with the intent dimension
added.