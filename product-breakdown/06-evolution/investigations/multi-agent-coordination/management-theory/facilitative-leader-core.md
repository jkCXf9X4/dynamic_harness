# Facilitative Leader — Core Theories (Netflix, Hackman, McChrystal)

Section 3.1–3.3 of the management-theory survey. Index: [README.md](README.md).
Continued: [facilitative-leader-safety.md](facilitative-leader-safety.md).

## 3.1 Context over control (Netflix)
**Source.** Netflix Culture Memo (<https://jobs.netflix.com/culture>), "People
over Process". Verified: *"We expect managers to practice context not control —
giving their teams the context and clarity needed to make good decisions instead
of trying to control everything themselves."* Companion: **highly aligned,
loosely coupled** — leaders align on goals, then teams operate independently.

**What it says.** Provide the *why*, the constraints, and available information;
let people decide the *how*. More decisions should be made low in the org ("how
few, not how many, decisions senior leaders make"). Coupling is *alignment-based*:
shared context permits autonomy without chaos. Managers remain involved but
**coach** and **step in only at risk points** — crisis, ethics, or lack of context.

**Design translation — the core of B-curated.** The `introduce` note is
**context** ("sibling X exists, here is why you may benefit, here are the shared
norms"), not control — the recipient chooses whether/how to engage. The parent
supplies **alignment** (roles, directions, connections); children are **loosely
coupled** (direct peer exchange, no approval per message). The parent "steps in"
only on risk signals: over-budget, escalation, a child without context — *not*
continuous. Guardrail: if a coordination step requires the parent to read or
forward a message's *content*, stop — that is control; redraw it as context.

## 3.2 Hackman: the five conditions of team effectiveness
**Source.** J. Richard Hackman, "Why Teams Don't Work" (HBR, May 2009);
*Leading Teams* (2002).

**The five conditions** (leader sets them up; then the team works):
1. **A real team** — clear, bounded membership, with interdependent task and
   shared responsibility. A team unclear about who is on it cannot perform.
2. **A compelling direction** — a challenging, clear, consequential goal.
3. **An enabling structure** — task design, *team norms*, and composition.
4. **A supportive organizational context** — resources, information, education.
5. **Expert coaching** — available but **periodic and minimal**: at the *start*,
   *midpoint/handoffs*, and *transitions* — not continuous supervision.

Hackman is explicit that leader *intervention* is most valuable at the team's
boundaries and transitions, not inside the work itself.

**Design translation.** Real team → the common-parent group (membership is who
the parent introduced). Compelling direction → each delegation's
description/role. Enabling structure → **the hardest to copy and the key
insight**: Hackman's *norms* map to the guardrail set (delivery caps,
summary-only messaging, escalate-on-conflict, advisory-not-authoritative),
encoded as *policy* (like `ToolPermissionPolicy`), not prompt text. Supportive
context → artifact store, provenance, budgets. Expert coaching → the parent
intervenes at connect, disconnect, and escalation only.

## 3.3 McChrystal: shared consciousness → empowered execution
**Source.** Stanley McChrystal, *Team of Teams* (2015), the NATO/JSOC
transformation: defeating a distributed network enemy required replacing
centralized command with a linked network.

**What it says.** **Trust requires a shared consciousness** — everyone sees
enough of the whole picture to make locally correct decisions without asking.
**Empowered execution** — once shared consciousness exists, units act
autonomously, decide locally, self-synchronize, no permission per move. The
leader's job is *building and maintaining the shared picture* (cross-unit
briefings, transparent dashboards, liaison officers), not directing every action.
**Trust-building via transparency** — the more people understand each other's
constraints, the more they cooperate directly.

**Design translation.** The **injection of sibling IDs + context** is the "shared
consciousness": each child knows who else holds relevant knowledge and *why* the
connection exists. **Empowered execution** = after injection, siblings
self-synchronize through direct exchange — no parent gate. The runtime's
telemetry/artifacts play the role of McChrystal's *dashboard*: a shared,
continuously updated picture that makes autonomous action safe.
