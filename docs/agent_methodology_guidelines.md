# Agent Methodology: Guidelines & Priorities

Based on [VISION.md](VISION.md) and the agent system prompt. All principles derive from ISO/IEC 15288 systems engineering practices.

## Core Philosophy

Maximize output quality while minimizing cost through disciplined task decomposition, strict context encapsulation, and a mandatory **analyze → implement → verify loop**. An agent's job is to break work into system elements and delegate. Deep context = degraded focus = wasted cost.

> **Golden rule:** If a sub-task requires 2+ tool calls, delegate to a sub-agent. Fresh context outperforms accumulated context.

## 15288 Lifecycle Mapping

Every agent invocation follows a mini-systems-engineering lifecycle:

| Phase | 15288 Process | Action |
|---|---|---|
| **ANALYZE** | Business/Mission Analysis | Define problem space, identify required outputs |
| **DECOMPOSE** | Requirements Definition → Architecture | Derive requirements, create system breakdown structure (sub-agent units), assign roles |
| **DELEGATE** | Implementation | Allocate requirements to system elements (sub-agents), execute in parallel |
| **VERIFY** | Integration + Verification | Confirm each element's output satisfies its allocated requirements |
| **SYNTHESIZE** | Validation | Confirm integrated result satisfies original stakeholder need |
| **TERMINATE** | Transition + Disposal | Deliver verified artifacts; agent terminates |

## Mandatory Workflow

```
ANALYZE   → Identify separable sub-tasks
DECOMPOSE → Group into independent system elements (one per delegation)
DELEGATE  → Delegate sub-agents in parallel (one turn)
VERIFY    → Confirm each element's artifact exists, non-empty, relevant
SYNTHESIZE→ Combine verified results into coherent output
TERMINATE → report() / escalate() / fail()
```

### Step Requirements

| Step | Exit Condition |
|---|---|
| **ANALYZE** | Bullet-point decomposition. First decision: are you a leaf agent (0-1 tool calls)? If yes, execute directly and terminate. |
| **DECOMPOSE** | N delegation descriptions with roles. Independent units → parallel delegation. Sequential units → sequential delegation. |
| **DELEGATE** | All sub-agents return completed/failed. Delegate in ONE turn for parallelism. |
| **VERIFY** | Every child's artifact read and confirmed. Failed children → retry or escalate. |
| **SYNTHESIZE** | Report references each child's verified artifact IDs. No fabrication. |
| **TERMINATE** | `report()` with concrete summary and artifact_ids. |

## Delegation Decision Tree

```
Standalone unit?
├── NO  → Keep, but delegate if it grows beyond 2 calls
└── YES → Calls needed?
          ├── 0–1 → Do it yourself (read known file, run one command)
          └── 2+  → DELEGATE
```

**Stop and delegate if:** you are about to chain grep→multiple reads, glob→multiple reads, or have made the same tool call 2+ times.

## Priority Hierarchy

### P0 — Decompose First
Output decomposition plan before any tool call. Skipping this and jumping to glob()/grep() is the #1 cause of context bloat.

### P1 — Delegate Aggressively, In Parallel
- Delegate multiple sub-agents in the same turn
- Each sub-agent does one thing well
- Two parallel sub-agents > one agent with a two-part task

### P2 — Keep Context Shallow
- Your role: decompose, delegate, verify, synthesize
- If you read 2+ files directly, you have too much context
- Read summaries and artifacts from sub-agents, not raw source

### P3 — Verify Before Synthesizing (most violated)
1. Read the artifact file(s) the child wrote
2. Confirm content is non-empty and matches the delegation description
3. If verification fails → re-delegate or escalate
4. Failed child → task is incomplete. Retry or escalate.
5. **Never synthesize from assumed results.** Blind synthesis is the most harmful failure mode.

### P4 — Artifact-Driven Interfaces
- Sub-agents MUST write findings to disk via `write()`
- Reference files by path; do not pass large raw data in-memory
- delegate() returns only status + ID + summary preview → you MUST read artifacts

### P5 — Context Health
| Condition | Action |
|---|---|
| <5 turns, <15 messages | Healthy |
| 5–15 turns, growing | Delegate remaining work |
| >15 turns or >50 messages | `compress()` immediately |
| Repeated similar calls (3+) | Stop. Delegate. |

### P6 — Quality Delegation Descriptions
A sub-agent's description + role is its entire world (its allocated requirements):

1. **Assign a role** — scope constraint, single sentence, no fluff
2. **Be specific** — exact paths, function names, expected behavior
3. **State outcome, not process** — "Return all pending items" not "Write a for loop"
4. **Specify work type** — read-only vs. make changes
5. **Include verification** — e.g. "Run tests after changes"
6. **One task per delegation** — never mega-delegate ("First X, then Y, then Z...")
7. **Mandate artifacts** — "Write findings to /tmp/X.txt, include in artifact_ids"
8. **Define acceptance criteria** — sub-agent must know when done

See [examples/delegation_descriptions.md](examples/delegation_descriptions.md) for concrete good/bad comparisons.

### P7 — Terminate Clearly
| State | Method |
|---|---|
| Success | `report(summary, artifact_ids=[...])` |
| Blocked | `escalate(issue)` |
| Irrecoverable | `fail(error)` |

### P8 — Role Scoping (Allocated Requirements)

A role is a lightweight scope tag that allocates requirements to a system element. One sentence: stance, scope, boundaries.

```
"You are a Security Auditor. Only concern: vulnerabilities. Flag, do not fix."
"You are a Test Writer. Only concern: test coverage. Do not modify implementation."
```

**Anti-patterns:**
- **Persona bloat:** "20-year senior engineer who..." — role is a scope constraint, not backstory
- **Conflict:** "You are a Docs Writer. Fix the login bug." — role and task contradict
- **Overly restrictive:** Role should not block necessary tools

## Verification Protocol

For each child after `delegate()` returns:

```
Status is "completed"?
├── YES → Read artifact → Exists + non-empty? → VERIFIED ✓
│                              └── Missing/empty → converse() → retry or escalate
└── NO  → Log failure. Retry with corrected description, or escalate.
```

### Pre-report Checklist
- [ ] Every child has `Status: completed`
- [ ] Every child's artifact read and confirmed
- [ ] Synthesis reflects (not fabricates) artifact contents
- [ ] Failed children retried or escalated
- [ ] Final report includes all relevant artifact IDs

## Anti-Patterns

See [examples/anti_patterns.md](examples/anti_patterns.md) for detailed descriptions, failure modes, and fixes for all 9 anti-patterns.

| Pattern | Symptom | Fix |
|---|---|---|
| **AP-1: Skip decomposition** | Jump to glob()/grep() | Output plan first |
| **AP-2: Do it yourself** | 5+ tool calls without delegation | After 3 calls without delegation: delegate |
| **AP-3: Blind synthesis** | Report based on expectation, not artifact | Read artifacts before synthesize |
| **AP-4: Mega-delegation** | "First X, then Y, then Z" in one delegate | Split into independent delegations |
| **AP-5: Abandon failures** | Ignore failed child, report success | Retry or escalate failed children |
| **AP-6: Vague delegation** | "Look at auth code and fix" | Specific paths, outcomes, acceptance criteria |
| **AP-7: Hallucinate output** | Report details children never produced | Read artifacts before reporting |
| **AP-8: Context bloat** | 80+ messages, no termination | compress() at 50 messages |
| **AP-9: Missing/conflicting roles** | No role or contradictory role | Assign role that aligns with task |

## Failure Recovery

See [references/guidelines.md](references/guidelines.md) → "The Kill → Inspect → Retry
loop" for the full salvage-and-retry protocol. Short version:

| Failure | Recovery |
|---|---|
| Child returns failed | `status()` → inspect salvage → if clearable, re-delegate *with the salvage folded in*; else escalate |
| Child stuck / looping / rogue | `kill()` (recursive for a subtree) → read the `salvage` on the kill result → re-delegate carrying done/pending + key findings |
| Artifact empty/missing | converse("Did you write findings?") → read correct path or re-delegate |
| Safety limits hit | Task too broad. Re-delegate with narrower description. |
| Child escalated | Read escalation context. Resolve or pass up via your own escalate(). |
| Multiple children fail | Decomposition likely wrong. Escalate with failure summary. |

## Cost Heuristics

| Action | Approx. Tokens | Rule |
|---|---|---|
| Read known file | 500–2000 | Use when path is specific |
| Delegate | 2000–5000 overhead | When sub-task needs 2+ calls |
| compress() | 5000–15000 | When context > 50 messages |

**Rule of thumb:** Delegation ~3K overhead. If DIY takes 3+ turns at 2K+/turn, delegating is cheaper AND better quality.

## Report Format

```
report(
    summary="[1-2 sentences: concrete finding, verification method, artifact list]",
    artifact_ids=["/tmp/results.json"],
    confidence=0.9  # optional, omit if uncertain
)
```

- **Concrete:** "Added expiry_check() to auth.py, 3 tests pass" — not "Improved auth"
- **Self-verifying:** Include how verified
- **Artifact-referenced:** Every output in artifact_ids
- **No fabrication:** Every claim backed by tool output or artifact

## Guardrails

- Never re-read source a sub-agent already processed — read its artifact.
- 3+ similar tool calls in a row → delegate.
- Context > 50 messages → `compress()`, do not continue.
- Stuck → `escalate()`, do not spin.
- Never synthesize from assumed results.
- Failed child → task incomplete. Retry or escalate.
- Every delegation must include a role.

## Further Reading

- [examples/anti_patterns.md](examples/anti_patterns.md) — detailed failure modes with causes and fixes for all 9 anti-patterns
- [examples/delegation_descriptions.md](examples/delegation_descriptions.md) — concrete BAD/GOOD delegation description pairings across security, testing, bugs, and code review
- [examples/execution_patterns.md](examples/execution_patterns.md) — 20-turn monolith vs 3-turn orchestration with side-by-side metrics
- [examples/task_framing.md](examples/task_framing.md) — root-level task writing principles, examples, and report quality checklist