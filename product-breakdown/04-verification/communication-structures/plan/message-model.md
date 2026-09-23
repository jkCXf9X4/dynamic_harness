---
title: "Plan — CommsMessage Model"
category: investigation / plan
parent: "README.md"
---

# CommsMessage — the typed envelope

```python
class CommsMessage(BaseModel):
    id: str                 # short opaque id (sender-prefixed)
    topic: str              # channel name; "" for by-ID messages
    kind: str               # "instruction" | "notification" | "question"
    sender_id: str          # agent that sent it
    recipients: list[str]   # agent ids; [] = topic subscribers
    stage: str              # "draft" | "revised" | "final" (self-scored)
    content: str            # the message; headline() truncates to ≤200 chars
    seq: int                # per-topic monotonic sequence (watermark cursor)
    created_at: datetime
```

Why this shape (from `../context-injection-design.md` §1–2):

- **`kind` names the authority.** `instruction` (parent → binding) vs
  `notification` (peer → advisory); the model triages without reading the body.
- **`headline` only; body behind a pointer.** A push is re-sent every remaining
  turn (push-multiplier), so the pushed surface stays ~200 chars. Body lives in
  the existing `ArtifactStore`/`ResultStore`; the agent pulls via the already-
  cacheable `read_artifact` / `result_read` tools.
- **`stage` + `topic` + recency** give cheap relevance metadata — the
  `[channel {topic}] {kind}: {sender} — {stage}` header as fields, so a
  `CommsDigestPolicy` or `read` output renders them without string-parsing.
