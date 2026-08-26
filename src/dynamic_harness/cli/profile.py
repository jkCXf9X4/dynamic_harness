"""Lightweight live-session profiler that produces developer-facing artifacts.

Enable with ``dynamic-harness --profile`` (+ optional ``--profile-dir``). When
active, a **sampling** profiler samples the interpreter stack on a fixed timer
for the entire session and, on exit, writes:

  profile/profile.txt    human-readable top-N table (sorted by self-time)
  profile/profile.json   machine-readable per-function aggregates + run metadata
  profile/meta.json      environment / version (easy to attach to an issue)

Sampling (rather than deterministic tracing like cProfile, which instruments
*every* Python call) is what keeps ``--profile`` cheap: overhead is one stack
grab per ``interval`` regardless of how hot the loop is, so the added cost is
roughly constant instead of scaling with the number of function calls.
"""

from __future__ import annotations

import importlib.metadata
import json
import platform
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# (file, line, name) -> [top_of_stack_samples, on_stack_samples]
_SampleKey = tuple[str, int, str]
_SampleRec = tuple[int, int]
_Stack = list[_SampleKey]


class _Sampler(threading.Thread):
    """Background thread that periodically captures the main thread's call stack
    and aggregates sample counts per function."""

    def __init__(self, interval: float, main_thread_id: int) -> None:
        super().__init__(name="handy-profiler", daemon=True)
        self.interval = interval
        self.main_tid = main_thread_id
        self._evt = threading.Event()
        self.samples: dict[_SampleKey, _SampleRec] = {}
        self.total: int = 0

    def stop(self) -> None:
        self._evt.set()
        self.join(timeout=0.5)

    def run(self) -> None:
        while not self._evt.is_set():
            started = time.perf_counter()
            frame = sys._current_frames().get(self.main_tid)
            if frame is not None:
                self._sample(frame)
            dt = time.perf_counter() - started
            self._evt.wait(max(0.0, float(self.interval) - dt))

    def _sample(self, frame: object) -> None:
        stack: _Stack = []
        cur = frame
        while cur is not None:
            code = cur.f_code
            stack.append((code.co_filename, code.co_firstlineno, code.co_name))
            cur = cur.f_back
        if not stack:
            return
        self.total += 1
        top = stack[0]
        for key in stack:
            rec = self.samples.setdefault(key, [0, 0])
            rec[1] += 1  # seen somewhere in the stack (cumulative proxy)
        self.samples[top][0] += 1  # at the top of the stack (self-time proxy)


class RunProfiler:
    """Sampling profiler wrapper. ``start()``/``stop()`` bracket the session."""

    def __init__(
        self,
        run_root: Path,
        *,
        enabled: bool = True,
        interval: float = 0.01,
    ) -> None:
        self.enabled = enabled
        self.interval = interval
        self._dir: Path | None = run_root / "profile" if enabled else None
        self._sampler: _Sampler | None = None
        self._started = False
        self._meta: dict[str, Any] = {}

    @property
    def active(self) -> bool:
        return self.enabled

    def start(self, *, meta: dict[str, Any] | None = None) -> None:
        """Begin sampling. ``meta`` becomes part of the produced artifact so the
        developer can see the environment + version the profile was captured on."""
        if not self.enabled:
            return
        if meta:
            self._meta.update(meta)
        if self._dir is not None:
            self._dir.mkdir(parents=True, exist_ok=True)
        self._sampler = _Sampler(self.interval, threading.current_thread().ident)
        self._sampler.start()
        self._started = True

    def stop(self) -> Path | None:
        """Stop sampling and write the profile artifacts. Returns the profile.txt
        path (or None when profiling is disabled / was never started)."""
        if not self.enabled or self._sampler is None or not self._started:
            return None
        self._sampler.stop()
        self._started = False
        return self._write()

    def _rows(self) -> list[dict[str, Any]]:
        assert self._sampler is not None
        rows = [
            {
                "file": file,
                "line": line,
                "name": name,
                "top_of_stack": is_top,
                "on_stack": on_stack,
            }
            for (file, line, name), (is_top, on_stack) in self._sampler.samples.items()
        ]
        rows.sort(key=lambda r: r["top_of_stack"], reverse=True)
        return rows

    def _write(self) -> Path:
        assert self._sampler is not None and self._dir is not None

        prof_path = self._dir / "profile.txt"
        rows = self._rows()
        total = self._sampler.total

        lines = [
            "Profile written by dynamic-harness --profile",
            "Meta:",
            json.dumps(self._meta, indent=2, default=str),
            "",
            f"samples: {total}  (interval: {self.interval:.5f}s)",
            "",
            "  self-count  name  file:line",
        ]
        for r in rows[:40]:
            lines.append(
                f"  {r['top_of_stack']:>9}  {r['name']}  "
                f"{r['file']}:{r['line']}"
            )
        prof_path.write_text("\n".join(lines) + "\n")

        overview = {
            "written_at": datetime.now(timezone.utc).isoformat(),
            "meta": self._meta,
            "sampling_interval": self.interval,
            "samples": total,
            "funcs_seen": len(rows),
            "top_self": rows[:80],
            "top_on_stack": sorted(rows, key=lambda r: r["on_stack"], reverse=True)[:50],
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