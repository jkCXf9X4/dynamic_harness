"""Cell 1 — parent-mediated: every peer exchange passes through the parent.

A message from a child to a *sibling* is re-routed to the common parent, who
relays it (the parent is the middle of the edge). Hierarchy edges stay direct.
No channels exist in this topology.
"""

from __future__ import annotations

from ..backend import CommsBackend, SendVerdict
from ..message import AgentRef, CommsMessage


class RelayBackend(CommsBackend):
    name = "relay"
    channels_enabled = False

    def _decide(self, sender: AgentRef, msg: CommsMessage) -> SendVerdict:
        target = msg.recipients[0] if msg.recipients else None
        if target is None or target == sender.agent_id:
            return SendVerdict.refuse("no valid recipient")
        if self._is_parent_of(sender.agent_id, target) or self._is_child_of(
            sender.agent_id, target
        ):
            return SendVerdict.ok([target])
        if self._is_sibling(sender.agent_id, target):
            parent = self._view.agent_parent_id(sender.agent_id)
            if parent:
                # The recipient field stays intact so the relaying parent knows
                # who the message is meant for.
                return SendVerdict.ok([parent])
        return SendVerdict.refuse(
            "peer communication is parent-mediated in this topology; "
            "unrelated agents cannot message each other directly"
        )