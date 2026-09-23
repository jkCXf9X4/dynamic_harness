# Report Format

```
report(
    summary="[1-2 sentences: concrete finding, verification method, artifact list]",
    artifact_ids=["/tmp/results.json"],
    confidence=0.9  # optional, omit if uncertain
)
```

- **Concrete:** "Added expiry_check() to auth.py, 3 tests pass" — not "Improved auth"
- **Self-verifying:** Include how verified
- **Artifact-referenced:** Every output in artifact_ids
- **No fabrication:** Every claim backed by tool output or artifact
