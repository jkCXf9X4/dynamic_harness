# Progressive Disclosure

## The Problem: Context Bloat

In a naive agent framework, a child agent might return 30,000 tokens of raw
findings to its parent. The parent's context window fills with data it may never
need. As the tree deepens, each ancestor carries the accumulated baggage of all
descendants.

## The Solution: Six Levels

Artifacts support six levels of detail, from headline to raw data:

```
headline       →  One-line summary (always populated)
summary_200    →  ~200 character summary
summary_1000   →  ~1000 character summary
technical      →  Technical details
full_report    →  Complete report
raw_data       →  Raw underlying data
```

## How It's Used

```
Parent agent delegates to Security Auditor child
  │
  ▼
Child completes → report(summary="Found 3 HIGH-severity vulns", files_written=["findings/findings.json"])
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
     → Returns the progressive summary (headline + summary views); deeper
       detail is withheld until the parent asks for it explicitly, e.g.
       read_artifact("abc123", file="findings.json") or level='full'.
  2. Parent decides: "I need more detail"
  3. read_artifact("abc123", level='full') / read the stored file
  4. Parent synthesizes and reports
```

The parent gets a 300-token preview, not a 30,000-token dump.
