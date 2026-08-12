from __future__ import annotations

import logging
from typing import Callable

from .task import Failure, ReportPayload, Escalation, BudgetRequest, ActivityEvent

logger = logging.getLogger(__name__)


def _dispatch(handlers: list[Callable], *args) -> None:
    """Fire handlers, isolating any handler failure from the agent loop.

    Event handlers are UI/logging glue; a bug in one must never propagate back
    and force-fail the agent that emitted the event.
    """
    for h in list(handlers):
        try:
            h(*args)
        except Exception as exc:  # noqa: BLE001
            logger.warning("event handler error: %s", exc)


class EventBus:
    def __init__(self) -> None:
        self._activity_handlers: list[Callable[[ActivityEvent], None]] = []
        self._report_handlers: list[Callable[[str, ReportPayload], None]] = []
        self._budget_handlers: list[Callable[[str, BudgetRequest], None]] = []
        self._escalation_handlers: list[Callable[[str, Escalation], None]] = []
        self._failure_handlers: list[Callable[[str, Failure], None]] = []

    def emit_activity(self, event: ActivityEvent) -> None:
        _dispatch(self._activity_handlers, event)

    def emit_report(self, agent_id: str, payload: ReportPayload) -> None:
        _dispatch(self._report_handlers, agent_id, payload)

    def emit_budget_request(self, agent_id: str, req: BudgetRequest) -> None:
        _dispatch(self._budget_handlers, agent_id, req)

    def emit_escalation(self, agent_id: str, esc: Escalation) -> None:
        _dispatch(self._escalation_handlers, agent_id, esc)

    def emit_failure(self, agent_id: str, fail: Failure) -> None:
        _dispatch(self._failure_handlers, agent_id, fail)

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
