# Delegation Quality (P6, P8)

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

### P8 — Role Scoping (Allocated Requirements)

A role is a lightweight scope tag that allocates requirements to a system
element. One sentence: stance, scope, boundaries.

```
"You are a Security Auditor. Only concern: vulnerabilities. Flag, do not fix."
"You are a Test Writer. Only concern: test coverage. Do not modify implementation."
```

**Anti-patterns:**
- **Persona bloat:** "20-year senior engineer who..." — role is a scope constraint, not backstory
- **Conflict:** "You are a Docs Writer. Fix the login bug." — role and task contradict
- **Overly restrictive:** Role should not block necessary tools

See [../examples/delegation_descriptions.md](../examples/delegation_descriptions.md)
for concrete BAD/GOOD pairings.
