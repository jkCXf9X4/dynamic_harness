# Relationship to Commits

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
        artifact_ids=[artifact.id],
        parent_ids=self.repository.commit_ids_for_tasks(parent_task_ids),
     )
     → repository.commit(commit)
```

The commit's `artifact_ids` hold the report artifact UUID. Files the agent wrote
are copied **into the artifact directory** under their basename and the
progressive-disclosure `raw_data` view is filled from them; the report's
`files_written` list is persisted as a `files_written.json` sidecar (a map of
declared → stored names) on the artifact. This makes the artifact self-contained
and provides end-to-end provenance from task to result.
