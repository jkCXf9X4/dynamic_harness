from __future__ import annotations

import shutil
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


class Repository:
    """Flat, append-only provenance store (one JSON line per commit).

    Commits live in a single ``commits.jsonl`` file; the parent/child DAG is
    rebuilt in memory on load. No sharding, no per-commit re-encoding.
    """

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._commits: dict[str, Commit] = {}
        self._task_commits: dict[str, str] = {}
        self._journal = self.root / "commits.jsonl"
        if self._journal.exists():
            self._load()

    def _load(self) -> None:
        with open(self._journal) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                c = Commit.model_validate_json(line)
                self._commits[c.id] = c
                self._task_commits[c.task_id] = c.id

    def _flush(self) -> None:
        """Rewrite the journal from the in-memory commit set (single source)."""
        tmp = self._journal.with_suffix(".jsonl.tmp")
        with open(tmp, "w") as f:
            for c in self._commits.values():
                f.write(c.model_dump_json() + "\n")
        tmp.replace(self._journal)

    def commit(self, commit: Commit) -> Commit:
        self._commits[commit.id] = commit
        self._task_commits[commit.task_id] = commit.id
        for pid in commit.parent_ids:
            parent = self._commits.get(pid)
            if parent and commit.id not in parent.child_ids:
                parent.child_ids.append(commit.id)
        self._flush()
        return commit

    def adopt_children_by_task(
        self, commit_id: str, child_task_ids: Sequence[str]
    ) -> None:
        """Link a commit to its children's commits by task id.

        Agent hierarchies commit children *before* their parent, so this is
        called after committing the parent to backfill the bidirectional links
        and keep the tree intact.
        """
        own = self._commits.get(commit_id)
        if own is None:
            return
        child_ids: list[str] = []
        for tid in child_task_ids:
            cid = self._task_commits.get(tid)
            if cid is not None and cid != commit_id:
                child_ids.append(cid)
        for cid in child_ids:
            if cid not in own.child_ids:
                own.child_ids.append(cid)
            child = self._commits.get(cid)
            if child is not None and commit_id not in child.parent_ids:
                child.parent_ids.append(commit_id)
        if child_ids:
            self._flush()

    def get(self, commit_id: str) -> Commit | None:
        return self._commits.get(commit_id)

    def commit_for_task(self, task_id: str) -> Commit | None:
        commit_id = self._task_commits.get(task_id)
        if commit_id is None:
            return None
        return self._commits.get(commit_id)

    def commit_ids_for_tasks(self, task_ids: Sequence[str]) -> list[str]:
        """Resolve task ids to their latest commit ids (for parent linkage)."""
        return [
            cid for tid in task_ids
            if (cid := self._task_commits.get(tid)) is not None
        ]

    def log(self, limit: int = 50) -> Sequence[Commit]:
        sorted_commits = sorted(self._commits.values(), key=lambda c: c.timestamp, reverse=True)
        return sorted_commits[:limit]

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

    def clear(self) -> None:
        self._commits.clear()
        self._task_commits.clear()
        if self.root.exists():
            shutil.rmtree(self.root)
            self.root.mkdir(parents=True, exist_ok=True)
            self._journal = self.root / "commits.jsonl"
