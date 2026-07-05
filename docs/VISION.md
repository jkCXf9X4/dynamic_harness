# VISION.md

## Vision Statement

**Dynamic Harness is a recursive agent runtime that maximizes LLM output quality while minimizing cost — by enforcing disciplined task decomposition, strict context encapsulation, and a mandatory analyze → implement → verify loop.**

---

## The Problem It Solves

LLM agents degrade under long-running tasks: context grows unbounded, focus drifts, and cost per turn scales linearly with history. Most agent frameworks treat the conversation **as the state**, which is the wrong abstraction for non-trivial work.

## The Core Insight

**Fresh context is cheaper than accumulated context.** A 3-turn sub-agent with a clean slate produces better results and costs less than a single agent grinding through 20+ turns of bloated context.

## Core Attributes

### 1. Recursive Task Decomposition

Parent agents spawn specialized child agents for each independent sub-task. Parents orchestrate — they do not do the work directly. This keeps every agent's context shallow and focused.

### 2. Analyze → Implement → Verify Loop

Every task flows through a mandatory pipeline:
```
ANALYZE     — Identify separable sub-tasks
DECOMPOSE   — Group into independent units of work
DELEGATE    — Spawn sub-agents in parallel (one turn)
VERIFY      — Read each child's artifacts, confirm non-empty and relevant
SYNTHESIZE  — Combine verified results into a coherent output
TERMINATE   — report() / escalate() / fail()
```
Verification is **not optional**. Never synthesize from assumed results. If a child cannot be verified, the task is not complete.

### 3. Context Encapsulation & Avoidance of Context Rot

Agents operate with **strict information hiding**:
- Know only: parent, children, assigned task
- No visibility into: siblings, cousins, global graph, other branches
- This prevents context pollution and keeps reasoning focused

The runtime owns the full task graph — agents never see it.

### 4. Artifact-Driven Communication

Findings persist to disk, not in-memory:
- Workers write results as **immutable artifacts** to disk
- Parents receive **structured summaries** + artifact IDs (~300 tokens, not 30,000)
- Detailed data is loaded **lazily**, only when a parent decides it needs it
- Progressive disclosure: headline → summary → technical summary → full report

This is a retrieval problem, not a communication problem.

### 5. Cost Effectiveness Through Fresh Context Economics

| Approach | Cost | Quality |
|---|---|---|
| Single agent, 20+ turns | Context bloat → degraded output, high token burn | Low — early context is stale |
| Decompose → 3 sub-agents × 3 turns each | 3× spawn overhead + fresh contexts | High — each agent is focused |

A spawn costs ~3K tokens overhead. Doing it yourself for 3+ turns at 2K+ tokens/turn is both more expensive **and** produces lower quality.

### 6. Disposable Workers

State lives in artifacts, not agent memory:
- Workers receive task + summary + artifact references
- Workers produce artifacts + structured report
- Workers terminate — they carry no history forward
- The artifact store is the source of truth, not any individual agent's context window

### 7. Parent-Defined Specialized Agents

Every parent defines exactly what its children are: their task scope, tools, and acceptance criteria. Sub-agents inherit only what the parent chooses to provide. This creates a **hierarchy of specialization** — each level of the tree narrows in focus and increases in precision.

## Architectural Pillars Summary

| Pillar | Principle |
|---|---|
| **Recursive decomposition** | Parents orchestrate, children execute; parents never do the work directly |
| **Context encapsulation** | Agents know only parent + children + task; no global visibility |
| **Artifact-driven communication** | Findings → disk; parents consume summaries, not raw context |
| **Verify before synthesize** | Every child's output is confirmed before aggregation |
| **Disposable workers** | State lives in immutable artifacts, not agent memory |
| **Fresh context economics** | 3-turn sub-agent > 20-turn monolithic agent |
| **Progressive disclosure** | Headline → summary → report; load details only when needed |
| **Git-like provenance** | Commits, immutable artifacts, branching, reproducibility |

## What This Is NOT

- **Not a chatbot framework** — conversations are not the state
- **Not a predefined workflow engine** — agents decide the decomposition dynamically
- **Not a code generation platform** — agents use tool calls, not generated code
- **Not a shared-memory system** — no global context, no agent registry accessible to workers

## Inspirations

- **Actor model** (Erlang, Akka) — private state, message passing, supervision trees
- **Distributed build systems** (Bazel, Nix) — tasks produce immutable artifacts, future tasks consume them
- **Operating systems** — virtual memory (lazy loading), process isolation, disposable processes
- **Git** — commits, immutable snapshots, provenance, branching/merging

## Success Criteria

A task is successful when:
1. Every sub-agent's output has been **verified** (artifact read, content confirmed)
2. The synthesis accurately reflects (does not fabricate) artifact contents
3. No failed child was abandoned — all failures were retried or escalated
4. The total context across all agents remained shallow (< messages per agent)
5. Cost was proportional to task complexity, not context duration