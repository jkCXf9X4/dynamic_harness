# Mandatory Workflow

```
ANALYZE   → Identify separable sub-tasks
DECOMPOSE → Group into independent system elements (one per delegation)
DELEGATE  → Delegate sub-agents in parallel (one turn)
VERIFY    → Confirm each element's artifact exists, non-empty, relevant
SYNTHESIZE→ Combine verified results into coherent output
TERMINATE → report() / escalate() / fail()
```

## Step Requirements

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

**Stop and delegate if:** you are about to chain grep→multiple reads,
glob→multiple reads, or have made the same tool call 2+ times.
