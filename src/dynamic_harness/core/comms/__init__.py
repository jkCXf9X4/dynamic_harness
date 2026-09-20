"""Swappable communication layer.

Public surface: the backend protocol/classes, the typed message model, the
channel-authority policy, and the config→backend factory. The layer is
host-agnostic — it never imports an agent or a runtime.
"""

from __future__ import annotations

from .backend import CommsBackend, ReadOutcome, SendVerdict, TopologyView
from .channel import ChannelPolicy
from .digest import CommsDigestPolicy, render_digest
from .factory import build_backend
from .log import CommsLog
from .message import (
    AgentRef,
    CommsMessage,
    TopicInfo,
    render_channel_envelope,
    render_incoming,
)

__all__ = [
    "CommsBackend",
    "ReadOutcome",
    "SendVerdict",
    "TopologyView",
    "ChannelPolicy",
    "CommsDigestPolicy",
    "render_digest",
    "build_backend",
    "CommsLog",
    "AgentRef",
    "CommsMessage",
    "TopicInfo",
    "render_channel_envelope",
    "render_incoming",
]