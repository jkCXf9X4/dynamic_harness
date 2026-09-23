# VISION

## Vision

**Dynamic Harness is a recursive agent runtime that maximizes LLM output quality
while minimizing cost — by enforcing disciplined task decomposition, strict
context encapsulation, and a mandatory analyze → implement → verify loop inspired
by ISO/IEC 15288 systems engineering.**

**Fresh context is cheaper than accumulated context.** A 3-turn sub-agent with a
clean slate produces better results and costs less than one agent grinding
through 20+ turns. Delegation overhead (~3K tokens) is below the cost of context
rot (>15K tokens for a 20-turn monolith).

## ISO/IEC 15288 Foundation

The V-model runs requirements down the left (analyze → decompose), implements at
the bottom (delegate), and verifies/validates back up the right (verify → synthesize).

| 15288 process | Phase | What happens |
|---|---|---|
| Business/Mission Analysis | ANALYZE | Define the problem space and required outcomes |
| Stakeholder Needs → Requirements + Architecture Definition | DECOMPOSE | Derive task requirements into a system breakdown structure and assign roles, scope, and interfaces — each requirement unit maps to one sub-agent (system element) |
| Implementation | DELEGATE | Sub-agents implement their allocated requirements, in parallel |
| Integration + Verification | VERIFY | Aggregate sub-agent artifacts; confirm interfaces are satisfied and each output meets its acceptance criteria |
| Validation | SYNTHESIZE | Confirm the integrated result satisfies the original task |
| Transition + Disposal | TERMINATE | Deliver verified artifacts via `report()`; the agent terminates — state lives in artifacts, not agent memory |

Verification is **not optional**; never synthesize from assumed results.

## Core Principles

1. **Recursive task decomposition.** Parents define requirements, then decompose
   into a hierarchy of system elements (sub-agents), each with an allocated
   requirement set (task + role). Parents orchestrate; they do not implement.
2. **Analyze → implement → verify (V-model).** ANALYZE → DECOMPOSE → DELEGATE →
   VERIFY → SYNTHESIZE → TERMINATE, every output traced to a requirement.
3. **Context encapsulation.** Agents know only parent, children, and allocated
   requirements — never siblings, cousins, or the architecture (Runtime-owned).
4. **Artifact-driven communication.** Findings persist to disk as immutable
   artifacts; parents get summaries + artifact IDs (~300 tokens, not 30,000).
5. **Progressive disclosure.** Artifacts expose layered views (headline →
   summary → report); parents consume the shallow tier and pull detail on demand.
6. **Fresh-context economics.** Decomposed 3×3-turn work beats a 20-turn monolith
   on both cost and quality (~3K delegation overhead < >15K context rot).
7. **Disposable workers.** State lives in artifacts, not agent memory; the store
   is the single source of truth and no worker carries history forward.
8. **Parent-defined specialized agents.** Every parent defines its children's
   scope, tools, and acceptance criteria; sub-agents inherit only that.
9. **Git-like provenance.** Commits, immutable artifacts, branching, and
   reproducibility.

## Boundaries and Inspirations

**What this is NOT:**

- **Not a chatbot framework** — conversations are not state.
- **Not a predefined workflow engine** — agents decide decomposition dynamically.
- **Not a code generation platform** — agents use tool calls, not generated code.
- **Not a shared-memory system** — no global context or element registry accessible to workers.

**Inspirations:**

- **ISO/IEC 15288** — systems engineering lifecycle, V-model, system breakdown.
- **Actor model** (Erlang, Akka) — private state, message passing, supervision.
- **Distributed build systems** (Bazel, Nix) — tasks produce immutable artifacts.
- **Operating systems** — virtual memory (lazy loading), process isolation, disposable processes.

## Success Criteria

1. Every sub-agent's output **verified** (artifact read, content confirmed).
2. Synthesis accurately reflects artifact contents (no fabrication).
3. No failed child abandoned — all failures retried or escalated.
4. Total context across all agents remains shallow.
5. Cost proportional to task complexity, not context duration.
