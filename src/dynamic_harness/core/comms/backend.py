"""CommsBackend — the swappable router + shared channel store.

The communication layer's core contract: **the routing decision lives entirely
in the backend**, so a cell switch is a construction change (one config key or
``Runtime(comms=...)``) and the tool surface never changes.

Host-agnostic: no agent or runtime import. The backend learns the tree shape
only through the ``TopologyView`` protocol (runtime-provided), and routes on
``AgentRef`` identities. The base class owns the shared channel machinery
(topic registry, append-only per-topic message log, per-(agent, topic)
watermarks); subclasses vary only the *routing decision* and whether channels
exist at all.

Delivery (injecting a routed message into a live agent) is the host's job —
the tools call ``continue_with_input`` / ``submit_input`` after reading a
``SendVerdict``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .channel import ChannelPolicy
from .message import AgentRef, CommsMessage, TopicInfo


class TopologyView(Protocol):
    """Minimal live view of the agent tree the backend routes against.

    Implemented by ``Runtime`` (duck-typed); tests provide a fake.
    """

    def agent_parent_id(self, agent_id: str) -> str | None: ...
    def agent_children_ids(self, agent_id: str) -> list[str]: ...
    def agent_role(self, agent_id: str) -> str | None: ...


@dataclass(frozen=True)
class SendVerdict:
    """Routing decision for one by-ID message.

    ``recipients`` are the *effective* delivery targets — they may differ from
    ``msg.recipients`` (e.g. the relay backend rewrites a peer message to the
    common parent). ``refusal`` is set when ``allowed`` is False.
    """

    allowed: bool
    recipients: list[str] = field(default_factory=list)
    refusal: str | None = None

    @classmethod
    def ok(cls, recipients: list[str]) -> "SendVerdict":
        return cls(allowed=True, recipients=list(recipients))

    @classmethod
    def refuse(cls, reason: str) -> "SendVerdict":
        return cls(allowed=False, refusal=reason)


@dataclass
class ReadOutcome:
    topic: str
    messages: list[CommsMessage] = field(default_factory=list)
    refusal: str | None = None


class CommsBackend:
    """Base router + channel store. Subclass to vary the routing decision."""

    name: str = "base"
    channels_enabled: bool = False
    peer_refusal_message: str = (
        "direct peer messaging is not available in this topology; "
        "use the channel tools (post/channel_read) instead"
    )

    def __init__(self, view: TopologyView, policy: ChannelPolicy) -> None:
        self._view = view
        self._policy = policy
        self._topics: dict[str, TopicInfo] = {}
        self._messages: dict[str, list[CommsMessage]] = {}
        # (agent_id, topic) -> last seen seq (per-subscriber delta read).
        self._watermarks: dict[tuple[str, str], int] = {}

    # -- identity helpers -------------------------------------------------

    def _is_parent_of(self, agent_id: str, parent_id: str) -> bool:
        """Is ``parent_id`` an ancestor of ``agent_id`` (any depth)?"""
        cur = self._view.agent_parent_id(agent_id)
        seen: set[str] = set()
        while cur is not None and cur not in seen:
            if cur == parent_id:
                return True
            seen.add(cur)
            cur = self._view.agent_parent_id(cur)
        return False

    def _is_child_of(self, agent_id: str, child_id: str) -> bool:
        """Is ``child_id`` a descendant of ``agent_id`` (any depth)?"""
        stack = [agent_id]
        seen: set[str] = set()
        while stack:
            cur = stack.pop()
            for kid in self._view.agent_children_ids(cur):
                if kid == child_id:
                    return True
                if kid not in seen:
                    seen.add(kid)
                    stack.append(kid)
        return False

    def _is_sibling(self, a: str, b: str) -> bool:
        pa = self._view.agent_parent_id(a)
        return pa is not None and pa == self._view.agent_parent_id(b)

    # -- routing: by-ID messaging (converse / message) ---------------------

    def route_message(self, sender: AgentRef, msg: CommsMessage) -> SendVerdict:
        """Default: direct along the parent-child hierarchy; peers refused.

        Subclasses relax (siblings: same-parent peers) or re-route (relay:
        peer message → the common parent) this decision. The hierarchy edge
        always stays direct in every topology — it is the control path.
        """
        target = msg.recipients[0] if msg.recipients else None
        if target is None or target == sender.agent_id:
            return SendVerdict.refuse("no valid recipient")
        if self._is_parent_of(sender.agent_id, target) or self._is_child_of(
            sender.agent_id, target
        ):
            return SendVerdict.ok([target])
        return SendVerdict.refuse(self.peer_refusal_message)

    # -- channels ----------------------------------------------------------

    def _normalize_topic(self, topic: str) -> str:
        """Map a caller's topic name onto this backend's channel(s)."""
        return topic

    def _no_channels_refusal(self) -> str:
        return (
            f"no topic channels in this topology ({self.name}); "
            "use converse/message for peer communication"
        )

    def post(
        self,
        sender: AgentRef,
        topic: str,
        content: str,
        kind: str = "notification",
        stage: str = "final",
    ) -> str | None:
        """Append a message to a topic. Returns a refusal reason or None."""
        if not self.channels_enabled:
            return self._no_channels_refusal()
        topic = self._normalize_topic(topic)
        if topic not in self._topics:
            allowed, why = self._policy.may_create(sender, topic, self._registry_snapshot())
            if not allowed:
                return f"cannot create topic '{topic}': {why}"
            self._topics[topic] = TopicInfo(name=topic, owner=sender.agent_id)
        info = self._topics[topic]
        msgs = self._messages.setdefault(topic, [])
        msg = CommsMessage(
            id=f"{sender.agent_id[:4]}-{len(msgs) + 1:04d}",
            topic=topic,
            kind=kind,
            stage=stage,
            sender_id=sender.agent_id,
            content=content,
            seq=len(msgs) + 1,
        )
        msgs.append(msg)
        info.last_activity = msg.created_at
        # The sender auto-subscribes so its own posts show up in channel_read.
        info.subscribers.add(sender.agent_id)
        return None

    def subscribe(self, agent: AgentRef, topic: str) -> str | None:
        if not self.channels_enabled:
            return self._no_channels_refusal()
        topic = self._normalize_topic(topic)
        if topic not in self._topics:
            allowed, why = self._policy.may_create(agent, topic, self._registry_snapshot())
            if not allowed:
                return f"cannot join unknown topic '{topic}': {why}"
            self._topics[topic] = TopicInfo(name=topic, owner=agent.agent_id)
        else:
            allowed, why = self._policy.may_join(agent, topic, self._registry_snapshot())
            if not allowed:
                return f"cannot subscribe to '{topic}': {why}"
        self._topics[topic].subscribers.add(agent.agent_id)
        return None

    def unsubscribe(self, agent: AgentRef, topic: str) -> str | None:
        if not self.channels_enabled:
            return self._no_channels_refusal()
        topic = self._normalize_topic(topic)
        info = self._topics.get(topic)
        if info is None:
            return f"unknown topic '{topic}'"
        info.subscribers.discard(agent.agent_id)
        return None

    def read(self, agent: AgentRef, topic: str) -> ReadOutcome:
        """Delta read: only messages newer than the agent's watermark for this
        topic, then advance the watermark. Pull-only and cache-safe."""
        if not self.channels_enabled:
            return ReadOutcome(topic=topic, refusal=self._no_channels_refusal())
        topic = self._normalize_topic(topic)
        if topic not in self._topics:
            return ReadOutcome(
                topic=topic,
                refusal=f"unknown topic '{topic}' (see `channels` for known topics)",
            )
        msgs = self._messages.get(topic, [])
        wm = self._watermarks.get((agent.agent_id, topic), 0)
        new = [m for m in msgs if m.seq > wm]
        if new:
            self._watermarks[(agent.agent_id, topic)] = new[-1].seq
        return ReadOutcome(topic=topic, messages=new)

    def channels(self, agent: AgentRef) -> list[dict[str, Any]]:
        if not self.channels_enabled:
            return [{"note": self._no_channels_refusal()}]
        out: list[dict[str, Any]] = []
        for name, info in sorted(self._topics.items()):
            snap = info.snapshot()
            snap["subscribed"] = agent.agent_id in info.subscribers
            out.append(snap)
        return out

    def subscriptions(self, agent_id: str) -> list[str]:
        return sorted(
            t for t, info in self._topics.items() if agent_id in info.subscribers
        )

    def channel_info(self, topic: str) -> dict[str, Any] | None:
        info = self._topics.get(self._normalize_topic(topic))
        return info.snapshot() if info is not None else None

    def _registry_snapshot(self) -> dict[str, Any]:
        return {name: info.snapshot() for name, info in self._topics.items()}