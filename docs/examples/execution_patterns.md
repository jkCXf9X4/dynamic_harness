# Execution Patterns: Good vs Bad

The difference between grinding through work yourself and orchestrating sub-agents. One approach burns tokens and degrades focus; the other stays lean and verified.

## BAD: Monolithic Grinding

```
Turn 1: glob("**/*.py")
Turn 2: read("file1.py")
Turn 3: read("file2.py")
Turn 4: read("file3.py")
Turn 5: grep("pattern", ...)
Turn 6: read("file4.py")    ← context now 18+ messages, focus lost
Turn 7: read("file5.py")
...
Turn 20: report("I analyzed the codebase...")  ← synthesis from stale/buried context
```

**Why it's bad:** 20 turns of manual grinding. Each turn adds context. By turn 10, the original task description is buried under system observations. Focus degrades. Cost scales linearly. No verification — the report summarizes stale context, not verified findings.

## GOOD: Orchestration with Delegation

```
Turn 1: [Analysis] "I see 3 sub-tasks: (A) find auth logic, (B) check error handling, (C) review tests"
         delegate(A), delegate(B), delegate(C)  ← all in one turn
Turn 2: [Verification] read_artifact(artA) / read("outputs/auth_findings.txt") ✓
         read("outputs/error_handling.txt") ✓
         read("outputs/test_review.txt") ✓
Turn 3: [Synthesis + Termination] report("...", artifact_ids=[artA, artB, artC])
```

**Total: 3 turns. Context: 9 messages. Cost: minimal. Quality: verified.**

**Why it's good:** Three parallel sub-agents, each with fresh context. Parent orchestrates and verifies. Each child produces a verified artifact. The parent synthesizes from verified facts, not assumptions.

---

## Comparison

| Metric | Monolithic | Orchestrated |
|---|---|---|
| Turns | 20 | 3 |
| Context messages | ~60 | ~9 |
| Cost | High (linear growth) | Low (fixed overhead per delegation) |
| Quality | Degraded (stale context) | High (fresh context per child) |
| Verification | None | Every child's artifact verified |
| Focus | Lost by turn 10 | Maintained throughout |