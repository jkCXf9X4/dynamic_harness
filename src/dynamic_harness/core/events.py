from __future__ import annotations

from typing import Callable

from .task import Failure, ReportPayload, Escalation, BudgetRequest, ActivityEvent


class EventBus:
    def __init__(self) -> None:
        self._activity_handlers: list[Callable[[ActivityEvent], None]] = []
        self._report_handlers: list[Callable[[str, ReportPayload], None]] = []
        self._budget_handlers: list[Callable[[str, BudgetRequest], None]] = []
        self._escalation_handlers: list[Callable[[str, Escalation], None]] = []
        self._failure_handlers: list[Callable[[str, Failure], None]] = []

    def emit_activity(self, event: ActivityEvent) -> None:
        for h in self._activity_handlers:
            h(event)

    def emit_report(self, agent_id: str, payload: ReportPayload) -> None:
        for h in self._report_handlers:
            h(agent_id, payload)

    def emit_budget_request(self, agent_id: str, req: BudgetRequest) -> None:
        for h in self._budget_handlers:
            h(agent_id, req)

    def emit_escalation(self, agent_id: str, esc: Escalation) -> None:
        for h in self._escalation_handlers:
            h(agent_id, esc)

    def emit_failure(self, agent_id: str, fail: Failure) -> None:
        for h in self._failure_handlers:
            h(agent_id, fail)

    def on_activity(self, handler: Callable[[ActivityEvent], None]) -> None:
        self._activity_handlers.append(handler)

    def on_report(self, handler: Callable[[str, ReportPayload], None]) -> None:
        self._report_handlers.append(handler)

    def on_budget_request(self, handler: Callable[[str, BudgetRequest], None]) -> None:
        self._budget_handlers.append(handler)

    def on_escalation(self, handler: Callable[[str, Escalation], None]) -> None:
        self._escalation_handlers.append(handler)

    def on_failure(self, handler: Callable[[str, Failure], None]) -> None:
        self._failure_handlers.append(handler)

    def clear(self) -> None:
        self._activity_handlers.clear()
        self._report_handlers.clear()
        self._budget_handlers.clear()
        self._escalation_handlers.clear()
        self._failure_handlers.clear()
