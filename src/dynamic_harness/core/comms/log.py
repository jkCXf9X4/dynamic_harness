"""Audit trail for the communication layer — append-only, machine-readable.

Every communication act (route verdict, post, delta read, subscription change,
delivery into a target's inbox) is one JSON line. The log is the single
cross-agent source of truth for "who sent what, who got it, did they read it,
and how did the topology route it" — it survives process exit and can be
followed live during execution (``tail -f``) or replayed post-hoc.

Best-effort by construction: a write failure (missing dir, disk full) is a
no-op so a recording hiccup can never fail or slow a run — the same invariant
as the per-agent ``TraceStore``.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class CommsLog:
    """Append-only JSONL sink for the communication layer.

    Thread-safe (the routing backends can be driven concurrently by sibling
    agents); one short line per record so concurrent appends never interleave.
    ``record`` never raises.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def record(self, **fields: Any) -> None:
        line = {"ts": datetime.now(timezone.utc).isoformat(), **fields}
        payload = json.dumps(line, default=str, ensure_ascii=False) + "\n"
        try:
            with self._lock:
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(payload)
        except OSError:
            pass