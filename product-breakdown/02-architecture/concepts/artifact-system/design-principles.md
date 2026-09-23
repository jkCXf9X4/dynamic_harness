# Design Principles

1. **Write to disk, not memory** — state is durable, not ephemeral
2. **Progressive loading** — summary first, details on demand
3. **Immutable** — write once, read many
4. **Provable** — every artifact is Git-tracked via commits
5. **Disposable agents** — agents terminate after reporting; their state lives in artifacts

## Hierarchical Summarization

```python
from dynamic_harness.artifact.summary import hierarchical_summary

# Generate an executive summary across multiple artifacts
summary = hierarchical_summary(artifact_ids, runtime.artifact_store)
```

The summarization system can combine multiple artifacts into a structured,
indented summary for overview purposes.

## Why Not In-Memory?

- **Scale:** in-memory state limits parallelism and persistence
- **Cost:** 30K tokens of raw context costs more than 300 tokens of summary
- **Reliability:** disk-backed artifacts survive crashes and timeouts
- **Inspection:** you can browse artifacts on disk without running the runtime
- **Versioning:** commits provide a permanent record of what happened
