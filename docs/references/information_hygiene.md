# Information Hygiene: Canonical State over Accumulated History

Why the runtime insists on lean, canonical state instead of accumulation — and how to
decide what to store. An agent that accumulates information instead of curating it
drowns its own context and stale the decisions of every future run that reads the state.

## Maintain canonical state, not historical accumulation

Whenever information changes, **remove, replace, or supersede** the stale representation.
Do not append new facts on top of old ones and leave both standing. The current state of
the world is one thing; the trail of how it got there is another, and only the former
belongs in canonical state. History is retained only when it has an explicit purpose and
a clearly defined home (e.g. a changelog the mission requires, or a commit log).

## Decide the disposition before storing

For every piece of information, determine *before* you store it which of these applies:

**create → update → replace → merge → supersede → remove**

The disposition is the point of the exercise: each new fact either extends an existing
canonical representation or invalidates it. If you cannot name the disposition, you have
not decided what the state should be — storing it anyway is how duplication and drift
begin.

## Excessive information is an anti-pattern

Unnecessary, redundant, outdated, or conflicting information raises cognitive load,
slows decisions, and creates ambiguity. It is not neutral: every extra fact is a chance
for a future agent to read the wrong one. Prefer the smallest set of information that
represents the current canonical state.

## Prevent duplication and contradiction

Before adding information, check whether an existing representation already covers it.
If it does, update that source of truth rather than creating a competing one. Two
representations of the same fact will eventually disagree, and then neither can be
trusted.

## Optimize for future retrieval and action

Structure state so a future agent can quickly determine **what is current**, **what is
authoritative**, and **what should be ignored**. State that cannot answer those three
questions on sight is mis-structured, regardless of how complete its content is.

## Minimum sufficient representation

When two representations carry the same actionable information, retain the simpler one.
Full transcripts and verbose detail are kept only when the smaller representation cannot
carry the decision-relevant content — and then they are kept in place of, never beside,
the summary.

## Complexity requires justification

Before adding a new abstraction, artifact, dependency, process, or layer, name the
concrete problem it solves. If no concrete problem is present, do not add it — a thing
that exists "in case it might help" is unpaid context tax for every future run.