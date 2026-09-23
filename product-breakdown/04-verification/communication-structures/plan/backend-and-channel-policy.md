---
title: "Plan — CommsBackend and ChannelPolicy"
category: investigation / plan
parent: "README.md"
---

# CommsBackend — the swappable router

```python
class CommsBackend:  # base class; subclasses vary only the routing decision
    name: str
    channels_enabled: bool

    def route_message(self, sender: AgentRef, msg: CommsMessage) -> SendVerdict:
        """The by-ID routing decision: allowed? effective recipients?"""

    def post(self, sender, topic, content, kind="notification", stage="final") -> str | None: ...
    def subscribe(self, agent: AgentRef, topic: str) -> str | None: ...
    def unsubscribe(self, agent: AgentRef, topic: str) -> str | None: ...
    def read(self, agent: AgentRef, topic: str) -> ReadOutcome:
        """Delta read; per-(agent, topic) watermark advances on read."""
    def channels(self, agent: AgentRef) -> list[dict]: ...
    def channel_info(self, topic: str) -> dict | None: ...
```

- **The routing decision lives entirely inside `route_message`.** Cell 1 rewrites
  non-parent recipients to the common parent; cell 2 refuses peers whose parents
  differ; cells 3/4 allow only hierarchy edges and route channel traffic by
  topic. Same tool call, different router.
- **`channel_read` is the pull path; `converse`/`message` are the push paths.**
  Cells 3/4 are pull-first; cells 1/2 add the blocking wait inside `converse`.
- **Watermarks are per-(agent, topic), owned by the backend** — the model never
  passes cursors; `read` returns only new items and advances the cursor (an empty
  re-read returns "no new messages").

## ChannelPolicy — creation/join authority

Cell 4's real variable is not "topics exist" but **who may create them**
(`../channel-context-design.md`):

```python
class ChannelPolicy:
    """Decides whether an agent may create/join a topic. No agent/runtime import."""
    def may_create(self, agent_id, parent_id, topic, existing) -> tuple[bool, str]: ...
    def may_join(self, agent_id, parent_id, topic) -> tuple[bool, str]: ...
```

- Default **parent-authorized**: `may_create` is true only for the root / the
  topic originator's parent; creation at a delegation boundary (team founding).
- **Anarchic registration** (any node may create) is a *second cell 4 variant* to
  measure sprawl/contamination against — report both.
- Same pattern as `SpawnPolicy`: pure decision; the backend performs the mutation.
