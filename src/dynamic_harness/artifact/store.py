from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence
from uuid import uuid4

from pydantic import BaseModel, Field


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

    def _artifact_dir(self, artifact_id: str) -> Path:
        d = self.root / artifact_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def write_text(self, artifact_id: str, name: str, content: str) -> Path:
        p = self._artifact_dir(artifact_id) / name
        p.write_text(content)
        return p

    def read_text(self, artifact_id: str, name: str) -> str | None:
        p = self._artifact_dir(artifact_id) / name
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
