from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from .task import Task

if TYPE_CHECKING:
    from .agent import Agent


def _focus_dict(focus: Any) -> dict[str, Any]:
    """Serialize a FocusLedger into a plain dict for checkpoint persistence."""
    return {
        "objective": getattr(focus, "objective", None) or "",
        "acceptance": list(getattr(focus, "acceptance", None) or []),
        "deliverable": getattr(focus, "deliverable", None) or "",
        "pending": list(getattr(focus, "pending", None) or []),
        "done": list(getattr(focus, "done", None) or []),
    }


class AgentCheckpoint(BaseModel):
    """Structured, on-disk snapshot of an agent's running state.

    Captured automatically after every committed turn (and explicitly via the
    ``checkpoint`` tool), so an aborted or failed run can be resumed from a
    fresh process by rebuilding the Agent from this record — state lives in the
    immutable checkpoint, not only in agent memory.
    """

    agent_id: str
    agent_type: str | None = None
    session_id: str = ""
    task: Task
    focus: dict[str, Any] = {}
    messages: list[dict[str, Any]] = []
    checkpoint_notes: list[str] = []
    turn_counter: int = 0
    turn_order: list[str] = []
    turns: dict[str, list[dict[str, Any]]] = {}
    pruned: list[str] = []
    prune_markers: dict[str, dict[str, Any]] = {}
    terminated: bool = False
    updated_at: str = ""


class CheckpointStore:
    """Persists and reloads ``AgentCheckpoint`` records keyed by agent id."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, agent_id: str) -> Path:
        return self.root / f"{agent_id}.json"

    def save(self, agent: Agent) -> AgentCheckpoint:
        cp = AgentCheckpoint(
            agent_id=str(agent.id),
            agent_type=agent.agent_type,
            session_id=str(getattr(agent, "session_id", None) or agent.id),
            task=agent.task,
            focus=_focus_dict(agent.focus),
            messages=list(agent.context.messages),
            checkpoint_notes=list(getattr(agent, "_checkpoint_notes", []) or []),
            turn_counter=agent.context.turn_counter,
            turn_order=list(agent.context.turn_order),
            turns=dict(agent.context.turns),
            pruned=sorted(agent.context.pruned),
            prune_markers=dict(agent.context.prune_markers),
            terminated=(
                agent.outcome.report is not None
                or agent.outcome.failure is not None
                or agent.outcome.escalation is not None
            ),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        # Self-heal: the checkpoint root may have been recreated/removed since
        # construction (e.g. a session/workdir cleanup), so ensure it exists
        # before writing. A checkpoint is best-effort — callers decide whether a
        # failure here is fatal — but the common FileNotFoundError case is
        # transient and cheap to recover from.
        self.root.mkdir(parents=True, exist_ok=True)
        self._path(str(agent.id)).write_text(cp.model_dump_json(indent=2))
        return cp

    def load(self, agent_id: str) -> AgentCheckpoint | None:
        p = self._path(agent_id)
        if not p.exists():
            return None
        return AgentCheckpoint.model_validate_json(p.read_text())

    def list(self) -> list[AgentCheckpoint]:
        out: list[AgentCheckpoint] = []
        for p in sorted(self.root.glob("*.json")):
            try:
                cp = AgentCheckpoint.model_validate_json(p.read_text())
            except Exception:
                continue
            out.append(cp)
        return out

    def list_ids(self) -> list[str]:
        return [cp.agent_id for cp in self.list()]

    def clear(self) -> None:
        if self.root.exists():
            shutil.rmtree(self.root)
            self.root.mkdir(parents=True, exist_ok=True)