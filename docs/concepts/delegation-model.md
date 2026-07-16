---
title: "Delegation Model"
category: concept
summary: >
  How recursive task decomposition works — the analyze → decompose → delegate
  → verify → synthesize loop. Parent agents orchestrate, children execute,
  and results flow up through artifact-driven communication.
related:
  - api/agent.md
  - api/runtime.md
  - api/tools.md
  - concepts/agent-lifecycle.md
  - concepts/artifact-system.md
---

# Delegation Model

Dynamic Harness uses **recursive task decomposition** — parent agents break work into independent sub-tasks, delegate to child agents, verify results, and synthesize a combined output. This is the core mechanism that keeps agent contexts shallow and output quality high.

## The Mandatory Workflow

Every agent (except leaf agents) follows this sequence:

```
ANALYZE → DECOMPOSE → DELEGATE → VERIFY → SYNTHESIZE → TERMINATE
```

### Step 1: ANALYZE

Read the task description. Identify all separable concerns. If the task is already narrow (one specific file, one command), skip to TERMINATE — you are a leaf agent.

### Step 2: DECOMPOSE

Group the work into independent units. Each unit becomes one delegation. Assign a **role** to each sub-agent that scopes its focus.

```
Task: "Audit the auth module for security and performance issues"

Decomposition:
  Unit A: Security audit → role: "Security Auditor"
  Unit B: Performance audit → role: "Performance Analyst"
```

Sequential dependencies stay as one unit. Independent units become parallel delegations.

### Step 3: DELEGATE

Call `delegate()` for each unit. **All delegations in one turn** for maximum parallelism. The delegate tool runs the child to completion before returning.

```
Turn 1: delegate(A), delegate(B)  ← Both in parallel
```

What the child sees:
- The delegation description (its entire world)
- The assigned role (scope constraint)
- Nothing from the grandparent or siblings

### Step 4: VERIFY

**This is the most frequently violated step.** After delegation returns:

1. Check the child's status — must be `completed`
2. Read the child's artifact file(s) — confirm they exist and are non-empty
3. Confirm the content matches the delegation description
4. If verification fails: re-delegate or escalate

**Never synthesize from assumed results.** Blind synthesis — reporting what you asked for instead of what the child found — is the most harmful failure mode.

### Step 5: SYNTHESIZE

Combine verified artifact contents into a coherent result. Reference all child artifact IDs.

### Step 6: TERMINATE

Call `report()` with a concrete, verifiable summary. Or `escalate()` if blocked. Or `fail()` if unrecoverable.

## The Delegation Decision Tree

Before every tool call, an agent decides:

```
Is this work a standalone unit?
├── NO  → Keep in your context (but beware accumulation)
└── YES → How many tool calls?
          ├── 0–1 calls → Do it yourself
          └── 2+ calls  → DELEGATE
```

**Delegation anti-signals** — stop and delegate immediately if:
- About to chain `grep` → multiple `read`s
- About to chain `glob` → multiple `read`s
- Made the same tool call 2+ times in this task

## Why Recursive Decomposition Works

### Fresh Context Economics

| Approach | Context | Quality | Cost |
|----------|---------|---------|------|
| Monolithic agent, 20 turns | Bloat, stale context | Degraded | High (per-turn scaling) |
| 3 sub-agents × 3 turns each | Fresh per sub-task | High (focused) | Delegation overhead ~3K tokens |

A delegation costs ~3K tokens overhead. Doing it yourself for 3+ turns at 2K+ tokens/turn is both more expensive and lower quality.

### Context Encapsulation

Agents know only:
- Their parent
- Their children
- Their assigned task

They never see:
- Siblings, cousins, the global task graph
- Work happening in other branches
- Historical context from ancestors

This forces each agent to be self-contained and prevents cross-contamination.

### Parallelism

Independent sub-tasks are delegated in the same tool-calling turn. The delegate tool runs each child to completion before returning, so the parent gets all results back in one response cycle.

## Parent-Child Contract

### Parent to Child

The parent provides:
- A specific, focused task description
- A role that scopes what the child cares about
- Acceptance criteria (what "done" looks like)
- Any necessary context (file paths, conventions)

### Child to Parent

The child returns (via `report()`):
- A concrete summary of findings
- Artifact IDs pointing to files on disk
- Optional confidence score

The child's raw context is never forwarded to the parent. This is the key to keeping parent contexts shallow.

## Failure Handling

| Failure | Recovery |
|---------|----------|
| Child returns `Status: failed` | Read failure reason. Retry with better description, or escalate |
| Child reports success but artifact empty | `converse(child_id, "...")`. Re-delegate if needed |
| Child hit safety limits | Task was too broad. Re-delegate with narrower scope |
| Multiple children all fail | Decomposition likely wrong. Escalate |
| Child escalated | Read escalation context. Resolve or pass up |

Never ignore failed children and synthesize partial results. A failed child means the task is incomplete.

## Leaf vs Orchestrator

Not every agent needs to delegate. **Leaf agents** execute directly:

```
Leaf agent heuristic:
  Task involves 0–1 tool calls on known targets → Execute directly → report()
  Task involves 2+ tool calls on unknown targets → You are an orchestrator → delegate
```

Examples of leaf tasks:
- "Read `src/main.py` and report the line count"
- "Run `pytest tests/test_auth.py -v` and report failures"
- "Read `/tmp/analysis.json` and summarize findings"

Examples of orchestrator tasks:
- "Audit the auth module for security issues"
- "Add test coverage for all untested functions in src/core/"
- "Refactor the error handling pattern across the codebase"

## Context Health Monitoring

The agent loop includes a Context Observation before each turn:

```
[Context Observation]
Turn: 7
Messages in context: 21
Estimated prompt tokens this agent: 12000
Your task: Audit the auth module...
```

Decision rules:

| Condition | Action |
|-----------|--------|
| <5 turns, <15 messages | Healthy — continue or delegate |
| 5–15 turns, growing messages | Delegate sub-agents for remaining work |
| >15 turns or >50 messages | Call `compress()` immediately |

## Roles

A role is a one-sentence scope constraint. It narrows the agent's solution space to prevent scope creep:

```
"You are a Security Auditor. Your only concern is vulnerabilities — flag issues, do not fix them."
"You are a Test Writer. Your only concern is test coverage. Do not modify implementation code."
```

Roles serve three purposes:
1. **Scope narrowing** — prevents the agent from wandering into unrelated concerns
2. **Token efficiency** — pre-answers decisions the agent would otherwise burn turns on
3. **Quality control** — ensures specialized work is done by specialized agents