from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from dynamic_harness.artifact.store import ArtifactStore
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.memory.repository import Repository


@pytest.fixture
def tmp() -> Path:
    return Path(tempfile.mkdtemp())


@pytest.fixture
def runtime(tmp: Path) -> Runtime:
    return Runtime(artifact_root=tmp / "artifacts", repo_root=tmp / "repo")


@pytest.fixture
def store(tmp: Path) -> ArtifactStore:
    return ArtifactStore(tmp)


@pytest.fixture
def repo(tmp: Path) -> Repository:
    return Repository(tmp)
