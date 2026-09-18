"""Cell 4 — topic channels: named topics with join/subscribe + watermarks.

The routing decision is topic-tagged: an agent posts to a topic, subscribers
read deltas. Creation is gated by ``ChannelPolicy`` (parent-authorized by
default; anarchic = the second experiment variant). Direct peer messaging is
hierarchy-only — peers coordinate through topics.
"""

from __future__ import annotations

from ..backend import CommsBackend, SendVerdict
from ..message import AgentRef, CommsMessage


class TopicsBackend(CommsBackend):
    name = "topics"
    channels_enabled = True

    def route_message(self, sender: AgentRef, msg: CommsMessage) -> SendVerdict:
        verdict = super().route_message(sender, msg)
        if verdict.allowed:
            return verdict
        return SendVerdict.refuse(
            "peers use topic channels (post/channel_read/subscribe); direct peer "
            "messaging is only allowed along the parent-child hierarchy"
        )