"""Channel creation/join authority — host-agnostic decision object.

The ``topics`` topology's real variable is not *that* topics exist but *who may
create them*. Default is parent-authorized (a boundary decision, mirroring the
dev investigation's team-founding): only the root, or a topic the parent
pre-declared in ``communication.channels``, may be created. ``anarchic`` is the
experiment's second cell-4 variant — any agent may create any topic, and the
comparison bed measures the sprawl/contamination it causes.

Pure decision: returns ``(allowed, reason)``; the backend performs the
mutation. No agent or runtime import.
"""

from __future__ import annotations

from typing import Any

from .message import AgentRef


class ChannelPolicy:
    def __init__(
        self,
        registration: str = "parent",
        allowed_topics: list[str] | None = None,
    ) -> None:
        self.registration = registration
        self._allowed = set(allowed_topics or [])

    def may_create(
        self, sender: AgentRef, topic: str, existing: dict[str, Any]
    ) -> tuple[bool, str]:
        """May ``sender`` create ``topic``? ``existing`` is the registry snapshot."""
        if self.registration == "anarchic":
            return True, ""
        if sender.parent_id is None:
            return True, ""  # root may create
        if topic in self._allowed:
            return True, ""  # pre-declared by the parent at the delegation boundary
        return False, (
            f"only the root may create topics, or a topic pre-declared in "
            f"communication.channels; '{topic}' is neither"
        )

    def may_join(
        self, sender: AgentRef, topic: str, existing: dict[str, Any]
    ) -> tuple[bool, str]:
        """Joining an existing topic is open in both modes — subscription is the
        agent's own routing choice; only *creation* is gated."""
        if topic in existing:
            return True, ""
        return False, "topic does not exist"