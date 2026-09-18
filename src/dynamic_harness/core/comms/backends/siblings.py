"""Cell 2 — same-parent siblings: children of one parent may message directly.

The hierarchy edge stays direct; a *peer* edge is allowed only when the two
agents share a parent (the parent remains the authority at the boundary).
Unrelated agents cannot message each other. No channels exist in this topology.
"""

from __future__ import annotations

from ..backend import CommsBackend, SendVerdict
from ..message import AgentRef, CommsMessage


class SiblingsBackend(CommsBackend):
    name = "siblings"
    channels_enabled = False

    def route_message(self, sender: AgentRef, msg: CommsMessage) -> SendVerdict:
        target = msg.recipients[0] if msg.recipients else None
        if target is None or target == sender.agent_id:
            return SendVerdict.refuse("no valid recipient")
        if self._is_parent_of(sender.agent_id, target) or self._is_child_of(
            sender.agent_id, target
        ):
            return SendVerdict.ok([target])
        if self._is_sibling(sender.agent_id, target):
            return SendVerdict.ok([target])
        return SendVerdict.refuse(
            "direct peer messaging is limited to same-parent siblings in this "
            "topology (plus your own parent/children); unrelated agents cannot "
            "message each other"
        )