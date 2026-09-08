from __future__ import annotations

import uuid
from collections import OrderedDict


class ResultStore:
    """Per-agent, memory-only, bounded store of tool-result snapshots.

    Every cacheable tool call has its full (untruncated) output stored here
    behind an opaque handle. A dedicated read-only tool (``result_read``) pages
    a snapshot by handle — it never re-executes the producing tool, which is
    what makes the cache safe for slow/expensive work: re-running is only ever
    invoked by calling the work tool again (no ``result_id`` arg on work tools).

    The store is deliberately NOT persisted to checkpoints and is cleared
    whenever an agent's in-memory context is reclaimed or its run resets: a
    resumed agent must never be served a stale snapshot from a previous
    process/session. An unknown handle fails loudly ("re-run the producing
    tool"), which is the safe default.
    """

    def __init__(self, max_entries: int = 32) -> None:
        self._max_entries = max(1, int(max_entries))
        self._entries: OrderedDict[str, str] = OrderedDict()

    def store(self, content: str) -> str:
        """Store a full tool output and return its handle."""
        handle = uuid.uuid4().hex[:12]
        self._entries[handle] = content
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)
        return handle

    def get(self, handle: str) -> str | None:
        """Return the snapshot text or None when unknown/evicted."""
        text = self._entries.get(handle)
        if text is not None:
            self._entries.move_to_end(handle)
        return text

    def clear(self) -> None:
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, handle: str) -> bool:
        return handle in self._entries