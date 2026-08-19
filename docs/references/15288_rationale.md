# Rationale: ISO/IEC 15288 Lifecycle

This is the durable, canonical statement of *why* the agent lifecycle is the way it
is. The live system prompt is an optimized, compressed derivation of these principles;
if a principle, term, or motivation has been optimized away from the prompt, consult
this file (via `read`) to recover the full rationale.

## Why a lifecycle at all

Dynamic Harness models each agent as a mini systems-engineering effort rooted in
**ISO/IEC 15288 — System and Software Engineering — System Life Cycle Processes**.
The standard defines a complete set of life-cycle processes covering the whole system
from concept through retirement. Modeling agents this way gives a shared vocabulary and
a mandatory discipline: you do not jump from a vague instruction to a finished artifact
in one leap. You **analyze** the need, **decompose** it into elements, allocate
requirements, **verify** each element's output against its requirement, and only then
**synthesize** a validated whole.

## The analyze→implement→verify loop

```
ANALYZE → DECOMPOSE → DELEGATE → VERIFY → SYNTHESIZE → TERMINATE
```

| Phase | 15288 process | Agent action |
|---|---|---|
| ANALYZE | Business / Mission Analysis | Clarify the in-scope problem and its required outputs. |
| DECOMPOSE | Requirements Definition → Architecture | Derive requirements, build a system breakdown of sub-agents, assign roles. |
| DELEGATE | Implementation | Allocate requirements to fresh sub-agents, run them in parallel. |
| VERIFY | Integration + Verification | Confirm every child's artifact satisfies its allocated requirement. |
| SYNTHESIZE | Validation | Confirm the integrated result satisfies the original stakeholder need. |
| TERMINATE | Transition + Disposal | Deliver verified artifacts; the element disposes of its state. |

This mirrors the **V-model**: requirements flow down on the left; verification flows up
on the right. Every artifact must be traceable up to the requirement that produced it,
and every requirement must be verified by an artifact before the task is complete.

## Why context encapsulation

15288 decomposes a system into *elements* that interact through defined interfaces but
otherwise stay isolated. Dynamic Harness applies the same principle to context: an agent
knows only its task, its parent, and its children. It never sees siblings, cousins, or
global state. This is not a limitation — it is the mechanism that keeps context shallow,
focus tight, and cost low. Fresh isolated context outperforms a long shared one.

## Why evidence on disk (artifact-driven interfaces)

15288 emphasizes defined interfaces and objective verification. In Dynamic Harness the
interface between an agent and its parent is the **disk artifact** written via `write()`
and referenced by `report()`. The report summary is only a *preview*; the artifact is the
*truth*. An unverifiable claim is not a result. `VERIFY EVERY CHILD` means: read the
artifact, confirm it is non-empty and matches the requirement, and never synthesize from
assumed results.
