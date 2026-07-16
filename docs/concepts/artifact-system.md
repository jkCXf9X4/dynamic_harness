---
title: "Artifact System"
category: concept
summary: >
  How progressive-disclosure artifacts work — six view levels from headline
  to raw data, enabling parents to consume summaries before loading full
  details. Artifacts are immutable, disk-backed, and Git-tracked.
related:
  - api/artifacts.md
  - api/repository.md
  - concepts/delegation-model.md
---

# Artifact System

Artifacts are the primary communication mechanism between agents. Instead of passing raw context between parent and child (which causes context bloat), agents write findings to disk as immutable artifacts. Parents read summaries first and progressively load more detail as needed.

## The Problem: Context Bloat

In a naive agent framework, a child agent might return 30,000 tokens of raw findings to its parent. The parent's context window fills with data it may never need. As the tree deepens, each ancestor carries the accumulated baggage of all descendants.

## The Solution: Progressive Disclosure

Artifacts support six levels of detail, from headline to raw data:

```
headline       →  One-line summary (always populated)
summary_200    →  ~200 character summary
summary_1000   →  ~1000 character summary
technical      →  Technical details
full_report    →  Complete report
raw_data       →  Raw underlying data
```

### How It's Used

```
Parent agent delegates to Security Auditor child
  │
  ▼
Child completes → report(summary="Found 3 HIGH-severity vulns", artifact_ids=["/tmp/findings.json"])
  │
  ▼
Runtime.deliver_report():
  → Creates ArtifactView(headline=summary[:200], summary_200=summary[:200])
  → Saves Artifact to ArtifactStore

Parent receives delegate() return:
  "Status: completed. Summary: Found 3 HIGH-severity vulns..."
  Artifact IDs: abc123

Parent VERIFIES:
  1. read_artifact("abc123")
     → Returns headline + summary_200 + summary_1000 views
  2. Parent decides: "I need more detail"
  3. read("/tmp/findings.json")
     → Gets the full detailed report
  4. Parent synthesizes and reports
```

The parent gets a 300-token preview, not a 30,000-token dump.

## Immutability

Artifacts are **write-once, never modified**. Once an agent calls `report()`, the Runtime creates the artifact and it becomes immutable. This ensures:

- **Reproducibility** — You can always revisit an artifact and get the same data
- **Traceability** — Every artifact is linked to a specific commit with timestamp
- **Safety** — No agent can retroactively modify another agent's work

```python
# Artifacts are created by the Runtime, not by agents directly:
# Inside Runtime.deliver_report():
view = ArtifactView(
    headline=payload.summary[:200],
    summary_200=payload.summary[:200],
    summary_1000=payload.summary[:1000],
)
artifact = Artifact(task_id=agent.task.id, agent_id=agent_id, views=view)
self.artifact_store.save(artifact)
```

## On-Disk Storage

```
<artifact_root>/
  abc123def456/
    artifact.json           # Serialized Artifact (metadata + views)
    findings.json            # File written by the agent via write()
    security_report.txt      # Another file written by the agent
  def789abc012/
    artifact.json
    analysis_results.json
```

The `artifact.json` file contains the serialized `Artifact` object with all view levels. Additional files are written by agents via the `write()` tool and referenced in `report(artifact_ids=[...])`.

## Relationship to Commits

Every artifact is linked to a commit in the Repository:

```
Agent.report(ReportPayload)
  │
  ▼
Runtime.deliver_report():
  1. artifact = Artifact(task_id, agent_id, views)
     → artifact_store.save(artifact)
  2. commit = Commit(
        task_id=agent.task.id,
        agent_id=agent_id,
        summary=payload.summary,
        artifact_ids=payload.artifact_ids + [artifact.id],
        parent_ids=[agent.task.parent_id] if parent else [],
     )
     → repository.commit(commit)
```

The commit's `artifact_ids` include both the report artifact and any files the agent wrote. This provides end-to-end provenance from task to result.

## Programmatic Access

```python
# From the artifact store
artifact = runtime.artifact_store.get(artifact_id)

# Progressive disclosure — ask for the right level
artifact.views.headline           # One line
artifact.views.summary_200        # ~200 chars
artifact.views.summary_1000       # ~1000 chars
artifact.views.technical           # Technical details
artifact.views.full_report         # Full report
artifact.views.raw_data            # Raw data

# Read files written by the agent
content = runtime.artifact_store.read_text(artifact_id, "findings.json")

# List all files in an artifact directory
files = runtime.artifact_store.list_files(artifact_id)
```

## Hierarchical Summarization

```python
from dynamic_harness.artifact.summary import hierarchical_summary

# Generate an executive summary across multiple artifacts
summary = hierarchical_summary(artifact_ids, runtime.artifact_store)
```

The summarization system can combine multiple artifacts into a structured, indented summary for overview purposes.

## Design Principles

1. **Write to disk, not memory** — State is durable, not ephemeral
2. **Progressive loading** — summary first, details on demand
3. **Immutable** — write once, read many
4. **Provable** — every artifact is Git-tracked via commits
5. **Disposable agents** — agents terminate after reporting; their state lives in artifacts

## Why Not In-Memory?

- **Scale:** In-memory state limits parallelism and persistence
- **Cost:** 30K tokens of raw context costs more than 300 tokens of summary
- **Reliability:** Disk-backed artifacts survive crashes and timeouts
- **Inspection:** You can browse artifacts on disk without running the runtime
- **Versioning:** Commits provide a permanent record of what happened