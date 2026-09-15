from __future__ import annotations

import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ArtifactView(BaseModel):
    headline: str = ""
    summary_200: str = ""
    summary_1000: str = ""
    technical: str = ""
    full_report: str = ""
    raw_data: str = ""

    @property
    def views(self) -> dict[str, str]:
        return {
            "headline": self.headline,
            "summary_200": self.summary_200,
            "summary_1000": self.summary_1000,
            "technical": self.technical,
            "full_report": self.full_report,
            "raw_data": self.raw_data,
        }


class Artifact(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    task_id: str
    agent_id: str
    views: ArtifactView = Field(default_factory=ArtifactView)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    path: Path | None = None

    def get_view(self, name: str) -> str:
        return self.views.views.get(name, self.views.headline)


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._artifacts: dict[str, Artifact] = {}
        self._load_existing()

    def _load_existing(self) -> None:
        for p in self.root.glob("*/artifact.json"):
            try:
                data = p.read_text()
                art = Artifact.model_validate_json(data)
                self._artifacts[art.id] = art
            except Exception:
                logger.warning("Failed to load artifact from %s", p, exc_info=True)

    def _validate_component(self, component: str) -> str:
        """Reject path components that could escape the store root."""
        if not component or component in (".", ".."):
            raise ValueError(f"Invalid artifact path component: {component!r}")
        if "/" in component or "\\" in component or "\x00" in component:
            raise ValueError(f"Invalid artifact path component: {component!r}")
        return component

    def _artifact_dir(self, artifact_id: str) -> Path:
        artifact_id = self._validate_component(artifact_id)
        d = self.root / artifact_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def write_text(self, artifact_id: str, name: str, content: str) -> Path:
        name = self._validate_component(name)
        d = self._artifact_dir(artifact_id)
        p = (d / name).resolve()
        if not p.is_relative_to(self.root):
            raise ValueError(f"Artifact path escapes store root: {name!r}")
        p.write_text(content)
        return p

    def read_text(self, artifact_id: str, name: str) -> str | None:
        name = self._validate_component(name)
        d = self._artifact_dir(artifact_id)
        p = (d / name).resolve()
        if not p.is_relative_to(self.root):
            raise ValueError(f"Artifact path escapes store root: {name!r}")
        return p.read_text() if p.exists() else None

    def list_files(self, artifact_id: str) -> Sequence[Path]:
        d = self._artifact_dir(artifact_id)
        return list(d.iterdir()) if d.exists() else []

    def save(self, artifact: Artifact) -> None:
        self._artifacts[artifact.id] = artifact
        artifact.path = self._artifact_dir(artifact.id)
        self.write_text(artifact.id, "artifact.json", artifact.model_dump_json(indent=2))

    def get(self, artifact_id: str) -> Artifact | None:
        return self._artifacts.get(artifact_id)

    def all(self) -> list[Artifact]:
        """All artifacts currently known to the store (loaded from disk)."""
        return list(self._artifacts.values())

    def clear(self) -> None:
        self._artifacts.clear()
        for child in self.root.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
