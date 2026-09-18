"""Typed communication model — the envelope every comms tool speaks.

The ``CommsMessage`` is the load-bearing shape for the whole communication
layer: ``kind`` names the authority (instruction from a parent = binding;
notification from a peer = advisory), ``headline`` keeps pushed surface tiny
(push-multiplier), and ``body_ref`` would point at heavier content pulled on
demand. ``AgentRef`` is the minimal sender identity the host-agnostic backends
route on; ``TopicInfo`` is the channel directory entry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CommsMessage(BaseModel):
    id: str
    topic: str
    kind: str = "notification"  # instruction | notification | question
    stage: str = "final"        # draft | revised | final
    sender_id: str
    recipients: list[str] = Field(
        default_factory=list,
        description="Target agent ids; empty = topic subscribers (channel post).",
    )
    content: str = ""
    seq: int = 0
    created_at: datetime = Field(default_factory=_utcnow)

    def headline(self) -> str:
        """≤200-char headline — the ONLY body pushed by default."""
        return " ".join(self.content.split())[:200]


@dataclass(frozen=True)
class AgentRef:
    """Minimal sender identity handed to the routing backends.

    Deliberately not an ``Agent``: keeps ``core/comms`` host-agnostic (no agent
    / runtime import), so the same backend can be exercised by a plugin host or
    a unit test with a fake topology view.
    """

    agent_id: str
    parent_id: str | None = None
    role: str | None = None


@dataclass
class TopicInfo:
    name: str
    owner: str | None
    subscribers: set[str] = field(default_factory=set)
    last_activity: datetime | None = None

    def snapshot(self) -> dict[str, Any]:
        return {
            "topic": self.name,
            "owner": self.owner,
            "subscribers": len(self.subscribers),
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
        }


def render_channel_envelope(msg: CommsMessage) -> str:
    """Public/read-side envelope (channel digest / channel_read output)."""
    sender = msg.sender_id[:8]
    return f"[channel {msg.topic}] {msg.kind}: {sender} — {msg.stage}\n{msg.headline()}"


def render_incoming(msg: CommsMessage) -> str:
    """Delivery-side envelope injected into a recipient's context.

    Carries sender + recipients + kind so the recipient knows WHO routed WHAT
    and whether it is binding (instruction) or advisory (notification) — the
    relevance triage the model needs without reading further.
    """
    to = (
        ", ".join(f"{r[:8]}" for r in msg.recipients)
        if msg.recipients
        else f"channel {msg.topic}"
    )
    head = f"[comms {msg.kind}] from {msg.sender_id[:8]} → {to}"
    if msg.stage != "final":
        head += f" ({msg.stage})"
    return f"{head}\n{msg.content}"