from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from .task import (
    BudgetRequest,
    Escalation,
    Failure,
    ReportPayload,
    SpawnRequest,
    Task,
)

if TYPE_CHECKING:
    from .runtime import Runtime


class Agent(ABC):
    def __init__(self, agent_id: str, task: Task, runtime: Runtime, parent: Agent | None = None) -> None:
        self.id = agent_id
        self.task = task
        self._runtime = runtime
        self.parent = parent
        self.children: list[Agent] = []

    @abstractmethod
    async def run(self) -> None: ...

    def spawn(self, description: str, **metadata: object) -> Agent:
        child_task = Task(description=description, parent_id=self.task.id, metadata=metadata)
        child = self._runtime.spawn_agent(child_task, parent=self)
        self.children.append(child)
        return child

    def report(self, payload: ReportPayload) -> None:
        self._runtime.deliver_report(self.id, payload)

    def request_more_budget(self, current_usage: int, requested: int, reason: str) -> None:
        req = BudgetRequest(task_id=self.task.id, current_usage=current_usage, requested=requested, reason=reason)
        self._runtime.deliver_budget_request(self.id, req)

    def escalate(self, issue: str, **context: object) -> None:
        e = Escalation(task_id=self.task.id, issue=issue, context=context)
        self._runtime.deliver_escalation(self.id, e)

    def fail(self, error: str, trace: str | None = None) -> None:
        f = Failure(task_id=self.task.id, error=error, trace=trace)
        self._runtime.deliver_failure(self.id, f)