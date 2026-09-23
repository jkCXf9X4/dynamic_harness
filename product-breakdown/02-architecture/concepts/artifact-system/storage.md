# Immutability, Storage & Access

## Immutability

Artifacts are **write-once, never modified**. Once an agent calls `report()`, the
Runtime creates the artifact and it becomes immutable. This ensures:

- **Reproducibility** — you can always revisit an artifact and get the same data
- **Traceability** — every artifact is linked to a specific commit with timestamp
- **Safety** — no agent can retroactively modify another agent's work

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

`artifact.json` contains the serialized `Artifact` object with all view levels.
Additional files are written by agents via the `write()` tool and referenced in
`report(artifact_ids=[...])`.

## Programmatic Access

```python
artifact = runtime.artifact_store.get(artifact_id)

artifact.views.headline           # One line
artifact.views.summary_200        # ~200 chars
artifact.views.summary_1000       # ~1000 chars
artifact.views.technical          # Technical details
artifact.views.full_report        # Full report
artifact.views.raw_data           # Raw data

content = runtime.artifact_store.read_text(artifact_id, "findings.json")
files = runtime.artifact_store.list_files(artifact_id)
```
