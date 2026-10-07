"""Persist run overview + event stream to files so the CLI stays prompt-only.

The terminal keeps prompts and a final outcome line; everything else that was
previously rendered live (agent tree, status, events) is written as JSON under
the run root for traceability and post-hoc / automated inspection.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..core.runtime import Runtime
from .present import (
    AgentNode,
    activity_brief,
    build_agent_tree,
    build_stats,
    fmt_usd,
    render_text_tree,
)


def _node_dict(node: AgentNode) -> dict[str, Any]:
    return {
        "agent_id": node.agent_id,
        "description": node.description,
        "status": node.status,
        "tokens": node.tokens,
        "messages": node.messages,
        "context_tokens": node.context_tokens,
        "prompt_tokens": node.prompt_tokens,
        "completion_tokens": node.completion_tokens,
        "cached_tokens": node.cached_tokens,
        "cache_hit_rate": node.cache_hit_rate,
        "cost_usd": node.cost_usd,
        "cum_cost_usd": node.cum_cost_usd,
        "artifact_ids": node.artifact_ids,
        "trace_path": node.trace_path,
        "activity": node.activity,
        "activity_age_s": node.activity_age_s,
        "children": [_node_dict(c) for c in node.children],
    }


class StateWriter:
    """Append-only ``events.jsonl`` plus latest ``agent_tree.json``/``stats.json``.

    All three sit in the run root (parent of the artifact root), next to
    ``artifacts/``, ``repo/``, and ``traces/`` for one-run overviews.
    """

    def __init__(self, run_root: Path, *, snapshot_interval: float = 5.0) -> None:
        self.root = Path(run_root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.tree_path = self.root / "agent_tree.json"
        self.stats_path = self.root / "stats.json"
        self.events_path = self.root / "events.jsonl"
        self.agents_txt_path = self.root / "agents.txt"
        # Throttle for activity-driven snapshots: don't rewrite the tree on
        # every LLM/tool event (build_agent_tree has a cost per call), only at
        # most once per interval. Terminal events and the CLI heartbeat's
        # flush() always bypass it.
        self.snapshot_interval = snapshot_interval
        self._last_snapshot = 0.0
        # agent_id → (epoch seconds, brief label) of the agent's most recent
        # activity event; feeds the per-agent age marker in the tree.
        self._last_activity: dict[str, tuple[float, str]] = {}

    def note_activity(self, agent_id: str, label: str, ts: float) -> None:
        """Record an agent's most recent activity (label + when it happened)."""
        self._last_activity[agent_id] = (ts, label)

    def snapshot(self, runtime: Runtime, *, force: bool = False) -> None:
        """Rewrite agent_tree.json + stats.json + agents.txt (text overview).

        Callers that fire frequently (activity events) omit ``force`` so the
        write is throttled to at most once per ``snapshot_interval``; terminal
        events (report / failure / escalation) pass ``force=True`` to guarantee
        the tree reflects the final state immediately.
        """
        now = time.monotonic()
        if not force and now - self._last_snapshot < self.snapshot_interval:
            return
        self._write(runtime)

    def flush(self, runtime: Runtime) -> None:
        """Time-based refresh for the CLI heartbeat.

        Bypasses the activity-event throttle — the heartbeat rate-limits
        itself — so ``tail -f agents.txt`` stays fresh even during long LLM
        calls, which emit no activity events while in flight.
        """
        self._write(runtime)

    def _write(self, runtime: Runtime) -> None:
        self._last_snapshot = time.monotonic()
        # Build the tree once and reuse for both JSON and text output (building
        # it twice doubles the provenance-index scan on every terminal event).
        stats = build_stats(runtime)
        nodes = build_agent_tree(runtime, last_activity=self._last_activity)
        generated_at = datetime.now(timezone.utc)
        self.tree_path.write_text(
            json.dumps([_node_dict(n) for n in nodes], indent=2)
        )
        self.stats_path.write_text(
            json.dumps(
                {**asdict(stats), "generated_at": generated_at.isoformat()},
                indent=2,
            )
        )
        header = (
            f"# generated {generated_at.strftime('%Y-%m-%dT%H:%M:%SZ')}"
            f" · {stats.agents} agents · ${fmt_usd(stats.cost_usd)}"
        )
        self.agents_txt_path.write_text(
            header + "\n" + render_text_tree(nodes)
        )

    def append_event(
        self, event: dict[str, Any], *, ts: datetime | None = None
    ) -> None:
        """Append one structured event to events.jsonl (never truncated)."""
        line = {"ts": (ts or datetime.now(timezone.utc)).isoformat(), **event}
        with open(self.events_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")


def attach_events(runtime: Runtime, writer: StateWriter) -> None:
    """Route runtime events to the writer; refresh snapshots on terminals."""

    def on_report(aid: str, payload: Any) -> None:
        writer.append_event({
            "event": "report",
            "agent_id": aid,
            "summary": payload.summary,
            "confidence": payload.confidence,
            "artifact_ids": payload.artifact_ids,
            "files_written": payload.files_written,
        })
        writer.snapshot(runtime, force=True)

    def on_failure(aid: str, fail: Any) -> None:
        writer.append_event({
            "event": "failure", "agent_id": aid, "error": fail.error,
        })
        writer.snapshot(runtime, force=True)

    def on_escalation(aid: str, esc: Any) -> None:
        writer.append_event({
            "event": "escalation", "agent_id": aid, "issue": esc.issue,
        })
        writer.snapshot(runtime, force=True)

    def on_activity(event: Any) -> None:
        writer.append_event({
            "event": "activity",
            "agent_id": event.agent_id,
            "event_type": event.event_type.value,
            "data": event.data,
        }, ts=event.timestamp)
        # Keep the tree fresh while work progresses (throttled), not only on
        # terminal events — and remember what each agent did last so the tree
        # can show a per-agent age marker.
        writer.note_activity(
            event.agent_id, activity_brief(event), event.timestamp.timestamp()
        )
        writer.snapshot(runtime)

    runtime.on_report(on_report)
    runtime.on_failure(on_failure)
    runtime.on_escalation(on_escalation)
    runtime.on_activity(on_activity)
    writer.snapshot(runtime)