from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest

from dynamic_harness.artifact.store import ArtifactStore
from dynamic_harness.core.agent import Agent
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import Task, TaskStatus
from dynamic_harness.memory.repository import Repository


@pytest.fixture
def tmp() -> Path:
    return Path(tempfile.mkdtemp())


@pytest.fixture
def runtime(tmp: Path) -> Runtime:
    return Runtime(artifact_root=tmp / "artifacts", repo_root=tmp / "repo", generated_root=tmp)


@pytest.fixture
def store(tmp: Path) -> ArtifactStore:
    return ArtifactStore(tmp)


@pytest.fixture
def repo(tmp: Path) -> Repository:
    return Repository(tmp)


# ── Test harness for agent interactions ──────────────────────────────

class AgentTest:
    """Helper for running and inspecting an agent in tests.

    Usage::

        at = AgentTest(runtime)
        await at.run("Find .py files and report")
        assert at.status == "completed"
        assert at.summary
    """

    def __init__(self, runtime: Runtime) -> None:
        self.runtime = runtime
        self.agent: Agent | None = None

    async def run(self, description: str, *, agent_type: str | None = None, **task_kwargs: Any) -> AgentTest:
        """Create and run an agent with the given task description."""
        task = Task(description=description, **task_kwargs)
        self.agent = self.runtime.delegate(task, agent_type=agent_type)
        await self.agent.run()
        return self

    @property
    def status(self) -> str:
        assert self.agent is not None
        return self.agent.task.status.value

    @property
    def summary(self) -> str:
        assert self.agent is not None and self.agent._last_report is not None
        return self.agent._last_report.summary

    @property
    def failure(self) -> str:
        assert self.agent is not None and self.agent._last_failure is not None
        return self.agent._last_failure.error


@pytest.fixture
def agent_test(runtime: Runtime) -> AgentTest:
    return AgentTest(runtime)
