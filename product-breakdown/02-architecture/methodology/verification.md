# Verification Protocol

For each child after `delegate()` returns:

```
Status is "completed"?
├── YES → Read artifact → Exists + non-empty? → VERIFIED ✓
│                              └── Missing/empty → converse() → retry or escalate
└── NO  → Log failure. Retry with corrected description, or escalate.
```

## Pre-report Checklist

- [ ] Every child has `Status: completed`
- [ ] Every child's artifact read and confirmed
- [ ] Synthesis reflects (not fabricates) artifact contents
- [ ] Failed children retried or escalated
- [ ] Final report includes all relevant artifact IDs
