from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class TraceStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _agent_dir(self, agent_id: str) -> Path:
        d = self.root / agent_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _append(self, agent_id: str, entry: dict[str, Any]) -> None:
        path = self._agent_dir(agent_id) / "trace.jsonl"
        with open(path, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")

    def record_llm_request(self, agent_id: str, messages: list[dict[str, Any]]) -> None:
        self._append(agent_id, {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "llm_request",
            "messages": messages,
        })

    def record_llm_response(self, agent_id: str, content: str | None, model: str, usage: dict | None, tool_calls: list[dict[str, Any]] | None = None) -> None:
        self._append(agent_id, {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "llm_response",
            "content": content,
            "model": model,
            "usage": usage,
            "tool_calls": tool_calls,
        })

    def record_tool_call(self, agent_id: str, tool_call_id: str, name: str, arguments: dict[str, Any]) -> None:
        self._append(agent_id, {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "tool_call",
            "tool_call_id": tool_call_id,
            "name": name,
            "arguments": arguments,
        })

    def record_tool_result(self, agent_id: str, tool_call_id: str, name: str, content: str) -> None:
        self._append(agent_id, {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "tool_result",
            "tool_call_id": tool_call_id,
            "name": name,
            "content_length": len(content),
            "content_preview": content[:500],
        })

    def record_event(self, agent_id: str, event: str, **kwargs: Any) -> None:
        self._append(agent_id, {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "event",
            "event": event,
            **kwargs,
        })

    def clear(self) -> None:
        if self.root.exists():
            shutil.rmtree(self.root)
            self.root.mkdir(parents=True, exist_ok=True)