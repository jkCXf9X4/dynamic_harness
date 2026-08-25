"""Persist run overview + event stream to files so the CLI stays prompt-only.

The terminal keeps prompts and a final outcome line; everything else that was
previously rendered live (agent tree, status, events) is written as JSON under
the run root for traceability and post-hoc / automated inspection.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..core.runtime import Runtime
from .present import AgentNode, build_agent_tree, build_stats, render_text_tree


def _node_dict(node: AgentNode) -> dict[str, Any]:
    return {
        "agent_id": node.agent_id,
        "description": node.description,
        "status": node.status,
        "tokens": node.tokens,
        "messages": node.messages,
        "prompt_tokens": node.prompt_tokens,
        "completion_tokens": node.completion_tokens,
        "cached_tokens": node.cached_tokens,
        "cache_hit_rate": node.cache_hit_rate,
        "artifact_ids": node.artifact_ids,
        "trace_path": node.trace_path,
        "children": [_node_dict(c) for c in node.children],
    }


class StateWriter:
    """Append-only ``events.jsonl`` plus latest ``agent_tree.json``/``stats.json``.

    All three sit in the run root (parent of the artifact root), next to
    ``artifacts/``, ``repo/``, and ``traces/`` for one-run overviews.
    """

    def __init__(self, run_root: Path) -> None:
        self.root = Path(run_root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.tree_path = self.root / "agent_tree.json"
        self.stats_path = self.root / "stats.json"
        self.events_path = self.root / "events.jsonl"
        self.agents_txt_path = self.root / "agents.txt"

    def snapshot(self, runtime: Runtime) -> None:
        """Rewrite agent_tree.json + stats.json + agents.txt (text overview)."""
        # Build the tree once and reuse for both JSON and text output (building
        # it twice doubles the provenance-index scan on every terminal event).
        nodes = build_agent_tree(runtime)
        self.tree_path.write_text(
            json.dumps([_node_dict(n) for n in nodes], indent=2)
        )
        self.stats_path.write_text(
            json.dumps(asdict(build_stats(runtime)), indent=2)
        )
        self.agents_txt_path.write_text(
            render_text_tree(nodes)
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
        writer.snapshot(runtime)

    def on_failure(aid: str, fail: Any) -> None:
        writer.append_event({
            "event": "failure", "agent_id": aid, "error": fail.error,
        })
        writer.snapshot(runtime)

    def on_escalation(aid: str, esc: Any) -> None:
        writer.append_event({
            "event": "escalation", "agent_id": aid, "issue": esc.issue,
        })
        writer.snapshot(runtime)

    def on_activity(event: Any) -> None:
        writer.append_event({
            "event": "activity",
            "agent_id": event.agent_id,
            "event_type": event.event_type.value,
            "data": event.data,
        }, ts=event.timestamp)

    runtime.on_report(on_report)
    runtime.on_failure(on_failure)
    runtime.on_escalation(on_escalation)
    runtime.on_activity(on_activity)
    writer.snapshot(runtime)