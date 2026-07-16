---
title: "Repository & Commit Reference"
category: api
module: dynamic_harness.memory.repository
classes:
  - Commit
  - Repository
summary: >
  Git-like provenance system. Every completed task creates a Commit with
  summary, artifact references, and parent/child links. Persisted as sharded
  JSON files on disk.
related:
  - api/runtime.md
  - api/artifacts.md
---

# Repository & Commit

```python
from dynamic_harness.memory.repository import Commit, Repository
```

The Repository provides Git-like provenance for agent work. Every completed task produces a `Commit` recording the summary, artifact references, and parent-child relationships. This enables traceability, reproducibility, and post-hoc analysis of the agent tree.

## `Commit`

```python
class Commit(BaseModel):
    id: str              # uuid4 hex, 12 chars, auto-generated
    task_id: str         # The task this commit records
    agent_id: str        # The agent that completed the work
    summary: str         # Report summary (from ReportPayload)
    artifact_ids: list[str]  # Artifact IDs including the report artifact
    parent_ids: list[str]    # Parent commit IDs (typically 0 or 1)
    child_ids: list[str]     # Child commit IDs (populated automatically)
    timestamp: datetime      # UTC, auto-generated
```

A commit is created automatically by `Runtime.deliver_report()` — you rarely create Commits directly.

### Parent/Child Linking

The Repository maintains bidirectional links:

```python
# When commit_a has child commit_b:
commit_a.child_ids = ["<commit_b_id>"]     # Populated automatically
commit_b.parent_ids = ["<commit_a_id>"]   # Set at creation
```

## `Repository`

### Constructor

```python
repo = Repository(root: Path)
```

On construction, the Repository loads all existing commits from disk (recursively finds all `commit.json` files under `root`).

### Methods

```python
# Create a commit (persists to disk, links parents automatically)
repo.commit(commit: Commit) -> Commit

# Look up by ID
repo.get(commit_id: str) -> Commit | None

# Recent commits (sorted by timestamp, newest first)
repo.log(limit: int = 50) -> Sequence[Commit]

# Build a parent->children tree
repo.tree(root_id: str | None = None) -> dict[str, list[str]]
# If root_id is provided, builds tree rooted at that commit
# If None, returns flat map of all commits to their children

# Count total commits
repo.count() -> int

# Clear all commits from memory
repo.clear() -> None
```

### On-Disk Structure

Commits are persisted as sharded JSON files:

```
<root>/
  ab/
    abc123def456/
      commit.json     # Serialized Commit (JSON)
  cd/
    cde789abc012/
      commit.json
  ...
```

The two-level sharding (first 2 chars of ID) distributes commits across directories, avoiding filesystem issues with many entries in a single directory.

### Example

```python
repo = Repository(Path("/tmp/repo"))

# Commits are created by the Runtime, but you can inspect:
commits = repo.log(limit=10)
for c in commits:
    print(f"{c.id[:8]} [{c.timestamp:%H:%M:%S}] {c.summary[:80]}")

# View the commit tree
tree = repo.tree()
# {"abc123": ["def456"], "def456": [], "ghi789": ["jkl012"], ...}

# Count
print(f"{repo.count()} commits recorded")
```

## Relationship to Other Systems

```
Agent.report(ReportPayload)
  │
  ▼
Runtime.deliver_report():
  1. artifact_store.save(Artifact)     → ArtifactStore records result
  2. repository.commit(Commit)         → Repository records provenance
     ├── commit.summary = payload.summary
     ├── commit.artifact_ids = payload.artifact_ids + [report_artifact.id]
     └── commit.parent_ids = [agent.task.parent_id]  (if parent exists)
```