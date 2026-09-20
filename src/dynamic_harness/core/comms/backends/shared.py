"""Cell 3 — one shared channel: every agent reads/writes a single topic.

Implemented as cell 4 with ONE topic and universal subscription (an append-only
log with per-agent delta reads — NOT a literal broadcast). Every post lands in
the shared topic regardless of the name used; ``subscribe`` is a no-op success
(everyone is subscribed); direct peer messaging is hierarchy-only, so peers
must use the channel. The measured context-health/contention cost of this cell
*is* the "everyone sees everything" verdict.
"""

from __future__ import annotations

from ..backend import CommsBackend, SendVerdict
from ..message import AgentRef, CommsMessage, TopicInfo


class SharedBackend(CommsBackend):
    name = "shared"
    channels_enabled = True

    def __init__(self, view, policy, *, shared_topic: str = "shared", log=None) -> None:
        super().__init__(view, policy, log=log)
        self._shared_topic = shared_topic
        self._topics[shared_topic] = TopicInfo(name=shared_topic, owner=None)

    def _normalize_topic(self, topic: str) -> str:
        return self._shared_topic

    def subscriptions(self, agent_id: str) -> list[str]:
        # Universal subscription: every agent sees the shared channel, so the
        # push digest treats it as subscribed regardless of join calls.
        return [self._shared_topic]

    def subscribe(self, agent: AgentRef, topic: str) -> str | None:
        # Universal subscription: trivially satisfied, never a failure.
        self._topics[self._shared_topic].subscribers.add(agent.agent_id)
        self._record("subscribe", topic=self._shared_topic, agent=agent.agent_id)
        return None

    def unsubscribe(self, agent: AgentRef, topic: str) -> str | None:
        self._topics[self._shared_topic].subscribers.discard(agent.agent_id)
        self._record("unsubscribe", topic=self._shared_topic, agent=agent.agent_id)
        return None

    def _decide(self, sender: AgentRef, msg: CommsMessage) -> SendVerdict:
        verdict = super()._decide(sender, msg)
        if verdict.allowed:
            return verdict
        return SendVerdict.refuse(
            "peers use the shared channel (post/channel_read); direct peer "
            "messaging is only allowed along the parent-child hierarchy"
        )