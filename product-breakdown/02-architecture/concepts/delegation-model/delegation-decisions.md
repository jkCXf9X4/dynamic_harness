# When to Delegate

## The Decision Tree

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

## Leaf vs Orchestrator

Not every agent needs to delegate. **Leaf agents** execute directly:

```
Leaf agent heuristic:
  Task involves 0–1 tool calls on known targets → Execute directly → report()
  Task involves 2+ tool calls on unknown targets → You are an orchestrator → delegate
```

Leaf tasks:
- "Read `src/main.py` and report the line count"
- "Run `pytest tests/test_auth.py -v` and report failures"
- "Read `/tmp/analysis.json` and summarize findings"

Orchestrator tasks:
- "Audit the auth module for security issues"
- "Add test coverage for all untested functions in src/core/"
- "Refactor the error handling pattern across the codebase"
