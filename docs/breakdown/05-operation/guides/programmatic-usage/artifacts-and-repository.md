---
id: INFO-121
type: info
title: Artifacts & Repository
summary: Programmatic access to artifacts and the repository, covering artifact views, agent-written files, commit history, and the commit tree.
date: 2026-09-23
status: current
---

# Artifacts & Repository

## Owns
- Programmatic reading of artifacts: views (headline, summary) and files written by agents
- Programmatic inspection of the repository: commit history and commit tree

## Excludes
- Runtime construction, arguments, and session management: INFO-127
- Delegation patterns and task graph inspection: INFO-123
- Custom agent classes: INFO-122
- No-LLM mode and error handling: INFO-124
- Event callbacks and usage tracking: INFO-125
- Complete integration example: INFO-126

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
