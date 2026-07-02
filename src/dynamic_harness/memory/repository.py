from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence
from uuid import uuid4

from pydantic import BaseModel, Field


class Commit(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    task_id: str
    agent_id: str
    summary: str = ""
    artifact_ids: list[str] = Field(default_factory=list)
    parent_ids: list[str] = Field(default_factory=list)
    child_ids: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    branch: str = "main"


def _commit_path(root: Path, commit_id: str) -> Path:
    return root / commit_id[:2] / commit_id / "commit.json"


class Repository:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._commits: dict[str, Commit] = {}
        self._load_existing()

    def _load_existing(self) -> None:
        for p in self.root.rglob("commit.json"):
            data = p.read_text()
            c = Commit.model_validate_json(data)
            self._commits[c.id] = c

    def commit(self, commit: Commit) -> Commit:
        self._commits[commit.id] = commit
        p = _commit_path(self.root, commit.id)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(commit.model_dump_json(indent=2))

        for pid in commit.parent_ids:
            parent = self._commits.get(pid)
            if parent and commit.id not in parent.child_ids:
                parent.child_ids.append(commit.id)
                self._save(parent)

        return commit

    def _save(self, commit: Commit) -> None:
        p = _commit_path(self.root, commit.id)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(commit.model_dump_json(indent=2))

    def get(self, commit_id: str) -> Commit | None:
        return self._commits.get(commit_id)

    def log(self, branch: str = "main", limit: int = 50) -> Sequence[Commit]:
        sorted_commits = sorted(self._commits.values(), key=lambda c: c.timestamp, reverse=True)
        return [c for c in sorted_commits if c.branch == branch][:limit]

    def tree(self, root_id: str | None = None) -> dict[str, list[str]]:
        tree: dict[str, list[str]] = {}
        if root_id:
            self._build_tree(root_id, tree)
        else:
            for c in self._commits.values():
                tree[c.id] = list(c.child_ids)
        return tree

    def _build_tree(self, commit_id: str, tree: dict[str, list[str]]) -> None:
        c = self._commits.get(commit_id)
        if not c:
            return
        tree[c.id] = list(c.child_ids)
        for child_id in c.child_ids:
            self._build_tree(child_id, tree)

    def count(self) -> int:
        return len(self._commits)