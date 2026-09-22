# VISION.md

## Vision Statement

**Dynamic Harness is a recursive agent runtime that maximizes LLM output quality while minimizing cost — by enforcing disciplined task decomposition, strict context encapsulation, and a mandatory analyze → implement → verify loop inspired by ISO/IEC 15288 systems engineering processes.**

## The Core Insight

**Fresh context is cheaper than accumulated context.** A 3-turn sub-agent with a clean slate produces better results and costs less than a single agent grinding through 20+ turns.

## ISO/IEC 15288 Systems Engineering Foundation

Dynamic Harness' agent workflow is structured as a systems engineering lifecycle:

| 15288 Process | Agent Phase | Description |
|---|---|---|
| Business/Mission Analysis | **ANALYZE** | Define problem space, identify what needs to change |
| Stakeholder Needs → Requirements | **DECOMPOSE** | Derive system (task) requirements into a system breakdown structure — each requirement unit maps to one sub-agent (system element) |
| Architecture Definition | **DECOMPOSE** | Assign roles, scope, and interfaces between sub-agents |
| Implementation | **DELEGATE** | Sub-agents (system elements) implement their allocated requirements |
| Integration | **VERIFY** | Aggregate sub-agent artifacts; confirm interfaces are satisfied |
| Verification | **VERIFY** | Confirm each sub-agent's output meets its defined acceptance criteria |
| Validation | **SYNTHESIZE** | Confirm the integrated result satisfies the original task (stakeholder need) |
| Transition | **TERMINATE** | Deliver verified artifacts via report() |
| Disposal | **TERMINATE** | Agent terminates — state lives in artifacts, not agent memory |

## Core Attributes

### 1. Recursive Task Decomposition (System Breakdown Structure)

Parent agents define system requirements, then decompose into a hierarchy of system elements (sub-agents). Each element receives an allocated requirement set — its task description and role. Elements may recursively decompose further. Parents orchestrate; they do not implement.

This mirrors 15288's system breakdown structure: a system (parent task) is recursively decomposed into system elements (sub-tasks) until each element is fully specified and independently implementable.

### 2. Analyze → Implement → Verify Loop (V-Model)

Every task flows through:
```
ANALYZE     — Define the problem space and required outcomes
DECOMPOSE   — Derive requirements, group into independent system elements
DELEGATE    — Implement via parallel sub-agents (one turn)
VERIFY      — Integrate and confirm each element's outputs
SYNTHESIZE  — Validate the integrated result against original requirements
TERMINATE   — report() / escalate() / fail()
```

This mirrors the V-model: requirements flow down the left side (analyze → decompose), implementation happens at the bottom (delegate), and verification/validation flows back up the right side (verify → synthesize).

Verification is **not optional**. Never synthesize from assumed results.

### 3. Context Encapsulation (System Element Isolation)

Agents operate with **strict information hiding**:
- Know only: parent, children, allocated requirements (task)
- No visibility into: siblings, cousins, global system architecture

The Runtime owns the full system architecture — agents never see it. This mirrors 15288's principle that system elements interact only through defined interfaces.

### 4. Artifact-Driven Communication (Defined Interfaces)

Findings persist to disk as immutable artifacts:
- Workers write results to disk — not in-memory
- Parents receive structured summaries + artifact IDs (~300 tokens, not 30,000)
- Detailed data is loaded lazily (progressive disclosure)

### 5. Cost Effectiveness Through Fresh Context Economics

| Approach | Cost | Quality |
|---|---|---|
| Single agent, 20+ turns | Context bloat → degraded output | Low |
| Decompose → 3 sub-agents × 3 turns | 3× delegation overhead + fresh contexts | High |

Delegation overhead (~3K tokens) < cost of context rot (>15K tokens for 20-turn monolith).

### 6. Disposable Workers (Stateless Elements)

State lives in artifacts, not agent memory. Workers receive allocated requirements, produce artifacts, and terminate. The artifact store is the single source of truth — no agent carries history forward.

### 7. Parent-Defined Specialized Agents (Allocated Requirements)

Every parent defines exactly what its children are: their allocated requirements (task scope), tools, and acceptance criteria. Sub-agents inherit only what the parent chooses to provide. Each decomposition level narrows focus and increases precision.

## Architectural Pillars

| Pillar | Principle |
|---|---|
| **Recursive decomposition** | System → system elements → subsystems; parents orchestrate, children implement |
| **V-model verification** | Requirements flow down, verification flows up; every output traced to a requirement |
| **Context encapsulation** | Elements know only parent + children + allocated requirements |
| **Artifact-driven interfaces** | Findings → disk; parents consume summaries via defined interfaces |
| **Verify before synthesize** | Every element's output confirmed before integration |
| **Disposable workers** | State in immutable artifacts; elements are stateless after termination |
| **Fresh context economics** | 3-turn element > 20-turn monolith |
| **Progressive disclosure** | Headline → summary → report; lazy loading of detail |
| **Git-like provenance** | Commits, immutable artifacts, branching, reproducibility |

## What This Is NOT

- **Not a chatbot framework** — conversations are not state
- **Not a predefined workflow engine** — agents decide decomposition dynamically
- **Not a code generation platform** — agents use tool calls, not generated code
- **Not a shared-memory system** — no global context, no element registry accessible to workers

## Inspirations

- **ISO/IEC 15288** — systems engineering lifecycle, V-model, system breakdown structure
- **Actor model** (Erlang, Akka) — private state, message passing, supervision trees
- **Distributed build systems** (Bazel, Nix) — tasks produce immutable artifacts
- **Operating systems** — virtual memory (lazy loading), process isolation, disposable processes

## Success Criteria

1. Every sub-agent's output **verified** (artifact read, content confirmed)
2. Synthesis accurately reflects artifact contents (no fabrication)
3. No failed child abandoned — all failures retried or escalated
4. Total context across all agents remains shallow
5. Cost proportional to task complexity, not context duration