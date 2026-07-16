---
title: "Artifact System Reference"
category: api
module: dynamic_harness.artifact.store
classes:
  - ArtifactView
  - Artifact
  - ArtifactStore
summary: >
  Progressive-disclosure artifact storage. Artifacts have six view levels
  (headline → full_report) enabling parents to read summaries before
  loading full details. Artifacts are immutable and persisted to disk.
related:
  - api/runtime.md
  - api/agent.md
  - concepts/artifact-system.md
---

# Artifact System

```python
from dynamic_harness.artifact.store import ArtifactView, Artifact, ArtifactStore
```

Artifacts are the primary communication mechanism between agents. Instead of passing raw context between parent and child, agents write findings to disk as immutable artifacts. Parents receive structured summaries and can progressively load more detail as needed.

## `ArtifactView` — Progressive Disclosure

Six levels of detail, from headline to raw data:

```python
class ArtifactView(BaseModel):
    headline: str = ""       # One-line summary
    summary_200: str = ""    # ~200 character summary
    summary_1000: str = ""   # ~1000 character summary
    technical: str = ""      # Technical details
    full_report: str = ""    # Complete report
    raw_data: str = ""       # Raw underlying data
```

### View Retrieval

```python
view: ArtifactView = artifact.views

# By attribute
view.headline       # One line
view.summary_200    # ~200 chars
view.summary_1000   # ~1000 chars
view.technical      # Detailed
view.full_report    # Complete
view.raw_data       # Raw

# By dict
view.views["headline"]           # Same as view.headline
artifact.get_view("technical")   # or .technical
```

The `headline` is always populated (from `report.summary[:200]`). Other views are filled based on artifact size — smaller artifacts may have data in all views; larger ones primarily use `headline` + `summary_200`.

## `Artifact` — An Immutable Result

```python
class Artifact(BaseModel):
    id: str              # uuid4 hex, 12 chars, auto-generated
    task_id: str         # The task that produced this
    agent_id: str        # The agent that produced this
    views: ArtifactView  # Progressive disclosure views
    created_at: datetime # UTC timestamp
    path: Path | None    # On-disk directory (set on save)
```

Artifacts are **immutable** after creation. They are created by the Runtime in `deliver_report()` — agents cannot modify artifacts after reporting.

## `ArtifactStore`

The central store. Manages both in-memory artifact objects and on-disk persistence.

```python
store = ArtifactStore(root: Path)
```

### Methods

```python
# Save an artifact (called by Runtime.deliver_report)
store.save(artifact: Artifact) -> None

# Retrieve by ID
store.get(artifact_id: str) -> Artifact | None

# Write/read text files within an artifact directory
store.write_text(artifact_id: str, name: str, content: str) -> Path
store.read_text(artifact_id: str, name: str) -> str | None

# List files in an artifact directory
store.list_files(artifact_id: str) -> Sequence[Path]

# Clear all artifacts
store.clear() -> None
```

### On-Disk Structure

```
<root>/
  <artifact_id>/
    artifact.json     # Serialized Artifact (JSON)
    ...               # Any additional files written via write_text()
```

### Typical Flow

```
Agent A runs → calls report(summary, artifact_ids=[...])
  │
  ▼
Runtime.deliver_report():
  1. Creates ArtifactView from report.summary
  2. Creates Artifact(task_id, agent_id, views)
  3. artifact_store.save(artifact)
     ├── Writes artifact.json to <root>/<id>/
     └── Stores in memory
  4. Repository.commit(commit)
     └── Links commit to artifact IDs

Agent B (parent) delegates → child returns → reads child's artifact:
  │
  ▼
agent.read_artifact(child_artifact_id)
  → Returns headline + summary_200 + summary_1000 (progressive views)
  → Parent decides if it needs technical/full_report
```

## Summarization

```python
from dynamic_harness.artifact.summary import summarize_artifact, hierarchical_summary
```

### `summarize_artifact(artifact, token_budget=2000) -> str`

Selects the best view level based on available token budget. Returns the most detailed view that fits within the budget.

### `hierarchical_summary(artifact_ids, artifact_store) -> str`

Renders an executive summary across multiple artifacts, indented hierarchically.

## Design Principles

1. **Immutable** — Artifacts are written once, never modified. This ensures reproducibility.
2. **Progressive disclosure** — Parents read summaries first, load details only when needed.
3. **Disk-backed** — State lives on disk, not in agent memory. Agents are disposable.
4. **Versionless** — Each report creates a new artifact. Git-like commits provide provenance.