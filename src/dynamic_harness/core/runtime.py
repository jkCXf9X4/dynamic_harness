from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable
from uuid import uuid4

from ..artifact.store import Artifact, ArtifactStore, ArtifactView
from ..memory.repository import Commit, Repository
from .agent import Agent
from .task import BudgetRequest, Escalation, Failure, ReportPayload, Task, TaskStatus

if TYPE_CHECKING:
    pass


class Runtime:
    def __init__(self, artifact_root: Path, repo_root: Path) -> None:
        self.artifact_store = ArtifactStore(artifact_root)
        self.repository = Repository(repo_root)
        self._agents: dict[str, Agent] = {}
        self._task_graph: dict[str, list[str]] = {}
        self._agent_factory: Callable[[str, Task, Runtime, Agent | None], Agent] | None = None

        self._report_handlers: list[Callable[[str, ReportPayload], None]] = []
        self._budget_handlers: list[Callable[[str, BudgetRequest], None]] = []
        self._escalation_handlers: list[Callable[[str, Escalation], None]] = []
        self._failure_handlers: list[Callable[[str, Failure], None]] = []

    def set_agent_factory(self, factory: Callable[[str, Task, Runtime, Agent | None], Agent]) -> None:
        self._agent_factory = factory

    def spawn_agent(self, task: Task, parent: Agent | None = None) -> Agent:
        assert self._agent_factory is not None, "agent_factory not set"
        agent_id = uuid4().hex[:12]
        agent = self._agent_factory(agent_id, task, self, parent)
        self._agents[agent_id] = agent
        self._task_graph[agent_id] = []
        if parent:
            self._task_graph.setdefault(parent.id, []).append(agent_id)
            task.parent_id = parent.task.id
        task.status = TaskStatus.running
        return agent

    def deliver_report(self, agent_id: str, payload: ReportPayload) -> None:
        agent = self._agents.get(agent_id)
        if not agent:
            return
        agent.task.status = TaskStatus.completed

        view = ArtifactView(
            headline=payload.summary[:200] if payload.summary else "",
            summary_200=payload.summary[:200],
            summary_1000=payload.summary[:1000],
        )
        artifact = Artifact(task_id=agent.task.id, agent_id=agent_id, views=view)
        self.artifact_store.save(artifact)

        commit = Commit(
            task_id=agent.task.id,
            agent_id=agent_id,
            summary=payload.summary,
            artifact_ids=payload.artifact_ids + [artifact.id],
            parent_ids=[agent.task.parent_id] if agent.task.parent_id else [],
        )
        self.repository.commit(commit)

        for h in self._report_handlers:
            h(agent_id, payload)

    def deliver_budget_request(self, agent_id: str, req: BudgetRequest) -> None:
        for h in self._budget_handlers:
            h(agent_id, req)

    def deliver_escalation(self, agent_id: str, esc: Escalation) -> None:
        agent = self._agents.get(agent_id)
        if agent:
            agent.task.status = TaskStatus.escalated
        for h in self._escalation_handlers:
            h(agent_id, esc)

    def deliver_failure(self, agent_id: str, fail: Failure) -> None:
        agent = self._agents.get(agent_id)
        if agent:
            agent.task.status = TaskStatus.failed
        for h in self._failure_handlers:
            h(agent_id, fail)

    def on_report(self, handler: Callable[[str, ReportPayload], None]) -> None:
        self._report_handlers.append(handler)

    def on_budget_request(self, handler: Callable[[str, BudgetRequest], None]) -> None:
        self._budget_handlers.append(handler)

    def on_escalation(self, handler: Callable[[str, Escalation], None]) -> None:
        self._escalation_handlers.append(handler)

    def on_failure(self, handler: Callable[[str, Failure], None]) -> None:
        self._failure_handlers.append(handler)

    def get_agent(self, agent_id: str) -> Agent | None:
        return self._agents.get(agent_id)

    def task_graph(self) -> dict[str, list[str]]:
        return dict(self._task_graph)

    def agent_count(self) -> int:
        return len(self._agents)

    def reset(self) -> None:
        self._agents.clear()
        self._task_graph.clear()