# Artifacts & Repository

## Working with Artifacts

```python
# After a task completes, read its artifacts
artifact = runtime.artifact_store.get(artifact_id)
if artifact:
    print(f"Headline: {artifact.views.headline}")
    print(f"Summary:  {artifact.views.summary_200}")

# Read files written by agents
content = runtime.artifact_store.read_text(artifact_id, "findings.json")
```

## Working with the Repository

```python
# View commit history
commits = runtime.repository.log(limit=20)
for c in commits:
    print(f"{c.id[:8]} [{c.timestamp:%H:%M}] {c.summary[:60]}")

# View commit tree
tree = runtime.repository.tree()
```
