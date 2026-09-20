"""Build the comms backend from config — the switching seam.

``topology: "off"`` (the default) returns ``None``: the communication layer is
deactivated and ``converse`` keeps today's global by-ID behavior. Any other
value constructs the corresponding cell backend.
"""

from __future__ import annotations

from ...config import CommsConfig
from .backend import CommsBackend, TopologyView
from .backends.relay import RelayBackend
from .backends.shared import SharedBackend
from .backends.siblings import SiblingsBackend
from .backends.topics import TopicsBackend
from .channel import ChannelPolicy
from .log import CommsLog

_OFF = {None, "", "off", "none", "disabled"}


def build_backend(
    config: CommsConfig | None,
    view: TopologyView,
    log: CommsLog | None = None,
) -> CommsBackend | None:
    if config is None or config.topology in _OFF:
        return None
    policy = ChannelPolicy(
        registration=config.registration, allowed_topics=config.channels
    )
    if config.topology == "relay":
        return RelayBackend(view, policy, log=log)
    if config.topology == "siblings":
        return SiblingsBackend(view, policy, log=log)
    if config.topology == "shared":
        return SharedBackend(view, policy, shared_topic=config.shared_topic, log=log)
    if config.topology == "topics":
        return TopicsBackend(view, policy, log=log)
    raise ValueError(
        f"unknown communication.topology {config.topology!r} "
        "(use off | relay | siblings | shared | topics)"
    )