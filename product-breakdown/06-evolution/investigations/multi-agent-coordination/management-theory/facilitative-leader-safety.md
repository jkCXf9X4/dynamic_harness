# Facilitative Leader — Safety & Brokerage (TMS, Aristotle, Edmondson, Servant)

Section 3.4–3.7 of the management-theory survey. Index: [README.md](README.md).
Previous: [facilitative-leader-core.md](facilitative-leader-core.md).

## 3.4 Transactive memory systems (Wegner): "who knows what"
**Source.** Daniel M. Wegner (1985; transactive memory and the "group mind" line).
Teams develop a **transactive memory system**: a shared directory of *who knows
what*, plus a meta-routine for retrieving knowledge from the right person.

**What it says.** Group performance depends less on everyone knowing the same
facts and more on **knowing who knows what** and being able to reach them.
Managers who *reshuffle* members or break established knowledge directories
degrade performance (preserving the team and its directory beats inserting
strangers). The meta-skill is **routing knowledge to where it's needed** — a
"broker" role that knows the landscape, not a relay for content.

**Design translation — the most direct theory for `introduce`.** The parent is
the **knowledge broker**: it holds the directory (children + their scopes), and
`introduce` is a **directory lookup + route** ("child A needs what child B
knows"). TMS warns that *disrupting* the group edge (constant reshuffling,
re-delegating the same knowledge to fresh strangers) is costly → keep the
`max_same_target_delegations`-style protection but extend the spirit: **prefer
introducing to a live child over spawning a fresh one.**

## 3.5 Google Project Aristotle: psychological safety first
**Source.** Project Aristotle (2012–2015), summarized in Charles Duhigg, "What
Google Learned From Its Quest to Build the Perfect Team," *NYT Magazine*, 2016.

**Findings.** The five dynamics of effective teams, in order: (1) **psychological
safety** — the belief you won't be punished or humiliated for speaking up, taking
risks, or making mistakes (Edmondson's construct); (2) dependability; (3)
structure & clarity; (4) meaning; (5) impact. The single strongest predictor is
**psychological safety**.

**Design translation.** Safety for agents = permission to be wrong and to ask.
Children must be able to admit a gap (`ask`), challenge a sibling's data
(escalate), decline an introduction, and correct their own report without
punishment. The existing `fail`/`escalate` paths are the safety valve; make
*surfacing* cheaper than *hiding* — children that ask for help are routed to an
introduction, not punished. Structure & clarity → every introduction carries a
*why*; every delegation carries role + acceptance criteria. Ambiguous membership
is fatal — hence explicit group boundaries.

## 3.6 Edmondson: psychological safety as a leader's job
**Source.** Amy Edmondson, *The Fearless Organization* (2018).

**What it says.** Leaders create the environment for speaking up: (1) frame work
as a learning problem ("there are unknowns"), (2) acknowledge their own
fallibility, (3) explicitly invite questions and challenge, (4) respond to input
constructively rather than punitively. **Framing failure as information**
separates "mistakes that inform the next attempt" from "reckless violations."

**Design translation.** The parent's *tone* toward children's failures should be
informational, not punitive: a failed child yields a diagnosis, then a
converse/resume/fresh decision — not a blame record. The system prompt already
leads here; the mechanism should too (failures carry *notes* forward to resume).

## 3.7 Leadership styles: servant and network leadership
**Servant leadership** (Robert Greenleaf, 1970): the leader's primary duty is
*serving* the team — removing obstacles, growing people, ensuring they have what
they need — rather than commanding. **Network/broker leadership** (Ronald Burt,
*Structural Holes*, 1992): value accrues to **brokers** who bridge structural
holes — groups that *don't otherwise connect*. Brokers don't accumulate
knowledge; they *route* it. (Granovetter's *Weak Ties*, 1973: novel,
non-redundant information travels across weak connections between separate
groups.)

**Design translation.** The parent is explicitly a **servant/broker**: it bridges
structural holes between its children (`introduce` connects two nodes that would
otherwise never meet) and *serves* by supplying context, then retreats. It is not
a knowledge accumulator. This also recommends **deliberately introducing children
with non-overlapping scopes** (a "weak tie" edge) to bring novel, non-redundant
information into a group — the systemic antidote to group-think.
