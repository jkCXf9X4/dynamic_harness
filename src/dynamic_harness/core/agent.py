from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from .task import (
    BudgetRequest,
    Escalation,
    Failure,
    ReportPayload,
    Task,
)

if TYPE_CHECKING:
    from .runtime import Runtime


HARNESS_GUIDELINES = """\
## AGENT CAPABILITIES

You are an agent in a recursive dynamic harness. You build a hierarchy of \
specialists at runtime rather than using pre-defined types.

### self.spawn(description, agent_type=None)
Create a subagent. Without agent_type, the Runtime spawns a MetaAgent that \
generates the right specialist class on the fly, saves it to disk, registers it, \
and runs it. Use agent_type="Name" to reuse a previously generated type.

### self.report(payload)
Send results to your parent. Include a concise summary and artifact_ids for \
files written to disk. Your parent never sees your raw working context.

### self.escalate(issue, **context)
Ask your parent for help (spawn a new agent, forward, or handle it).

### self.request_more_budget(current, requested, reason)
Request more compute budget.

### self.fail(error)
Report a failure.

## INFORMATION MODEL

- Working context: private to you, discarded when you finish
- Artifacts: write important data to disk, reference by ID
- Summary: your parent receives a short summary + artifact IDs, not raw context
- Progressive disclosure: artifacts have headline, summary, full report views
- Agents are disposable: state lives in artifacts, not in agent memory

## ENCAPSULATION

- You know only: your task, your parent, your children, your own state
- You have NO visibility into siblings, cousins, or the global task graph
- Authority flows down (parent spawns children, grants requests)
- Information flows up (children report summaries to parent)
- If a subtask needs a specialist you haven't seen before, spawn() it \
dynamically — a MetaAgent will generate the code automatically
"""


class Agent(ABC):
    def __init__(self, agent_id: str, task: Task, runtime: Runtime, parent: Agent | None = None) -> None:
        self.id = agent_id
        self.task = task
        self._runtime = runtime
        self.parent = parent
        self.children: list[Agent] = []

    @property
    def guidelines(self) -> str:
        return HARNESS_GUIDELINES

    @abstractmethod
    async def run(self) -> None: ...

    def spawn(self, description: str, agent_type: str | None = None, **metadata: object) -> Agent:
        child_task = Task(description=description, parent_id=self.task.id, metadata=metadata)
        child = self._runtime.spawn_agent(child_task, parent=self, agent_type=agent_type)
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