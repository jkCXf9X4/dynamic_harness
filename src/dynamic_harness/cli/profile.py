"""Lightweight live-session profiler that produces developer-facing artifacts.

Enable with ``dynamic-harness --profile`` (+ optional ``--profile-dir``). When
active, a ``cProfile`` sampler wraps the entire session and, on exit, writes
three files under the run root (or ``--profile-dir``):

  profile/profile.prof   binary cProfile dump — open with ``pstats``/snakeviz
  profile/profile.txt    human-readable top-N table (sorted by cumulative time)
  profile/profile.json   machine-readable per-function aggregates + run metadata
                         (easy to attach to an issue / paste into a tool)

The profile reflects the *whole live session* (batch or interactive), exactly
as it ran (including real LLM calls), so it is a faithful diagnostic to hand
back to a developer instead of a synthetic micro-benchmark.
"""

from __future__ import annotations

import cProfile
import importlib.metadata
import io
import json
import pstats
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RunProfiler:
    def __init__(self, run_root: Path, *, enabled: bool = True) -> None:
        self.enabled = enabled
        self._dir: Path | None = run_root / "profile" if enabled else None
        self._prof = cProfile.Profile() if enabled else None
        self._started = False
        self._meta: dict[str, Any] = {}

    @property
    def active(self) -> bool:
        return self.enabled

    def start(self, *, meta: dict[str, Any] | None = None) -> None:
        """Begin sampling. ``meta`` becomes part of the produced artifact so the
        developer can see the environment + version the profile was captured on."""
        if not self.enabled or self._prof is None:
            return
        if meta:
            self._meta.update(meta)
        if self._dir is not None:
            self._dir.mkdir(parents=True, exist_ok=True)
        self._prof.enable()
        self._started = True

    def stop(self) -> Path | None:
        """Stop sampling and write the profile artifacts. Returns the .prof path
        (or None when profiling is disabled / was never started)."""
        if not self.enabled or self._prof is None or not self._started:
            return None
        self._prof.disable()
        self._started = False
        return self._write()

    def _write(self) -> Path:
        assert self._prof is not None and self._dir is not None

        prof_path = self._dir / "profile.prof"
        self._prof.dump_stats(str(prof_path))

        # Human-readable top table (also reflects aggregated cumulative time).
        buf = io.StringIO()
        ps = pstats.Stats(self._prof, stream=buf)
        ps.strip_dirs()
        ps.sort_stats("cumulative")
        ps.print_stats(40)
        (self._dir / "profile.txt").write_text(
            "Profile written by dynamic-harness --profile\n"
            "Meta:\n"
            + json.dumps(self._meta, indent=2, default=str)
            + "\n\n"
            + buf.getvalue()
        )

        # Machine-readable aggregates + run metadata.
        stats = pstats.Stats(self._prof)
        stats.strip_dirs()
        rows: list[dict[str, Any]] = []
        for func, (cc, nc, tt, ct, _callers) in stats.stats.items():
            filename, lineno, name = func
            rows.append({
                "file": filename,
                "line": lineno,
                "name": name,
                "ncalls": nc,
                "tottime": tt,
                "cumtime": ct,
            })
        rows.sort(key=lambda r: r["cumtime"], reverse=True)
        overview = {
            "written_at": datetime.now(timezone.utc).isoformat(),
            "meta": self._meta,
            "top_cumtime": rows[:80],
            "top_tottime": sorted(rows, key=lambda r: r["tottime"], reverse=True)[:50],
        }
        (self._dir / "profile.json").write_text(json.dumps(overview, indent=2))
        (self._dir / "meta.json").write_text(json.dumps(self._meta, indent=2, default=str))
        return prof_path


def run_meta(args: Any) -> dict[str, Any]:
    """Capture environment + version metadata to attach to a profile artifact."""
    try:
        version = importlib.metadata.version("dynamic-harness")
    except importlib.metadata.PackageNotFoundError:
        version = "unknown (editable install?)"
    return {
        "version": version,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "argv": list(sys.argv),
        "interactive": (
            bool(getattr(args, "interactive", False))
            or not any(getattr(args, k, None) for k in ("prompt", "m", "resume"))
        ),
        "model": getattr(args, "model", None),
        "resume": getattr(args, "resume", None),
        "prompt_chars": sum(len(p) for p in getattr(args, "prompt", []) or []),
    }
