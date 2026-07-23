from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from .task import ActivityEventType, Failure, ReportPayload, Escalation, BudgetRequest, ActivityEvent


@dataclass
class IterationData:
    turn: int
    messages: int
    prompt_tokens: int


@dataclass
class LLMCallEndData:
    model: str
    prompt_tokens: int
    completion_tokens: int
    tool_calls: list[str]


@dataclass
class ToolCallStartData:
    tool_name: str
    arguments: dict[str, Any]


@dataclass
class ToolCallEndData:
    tool_name: str
    result_length: int
    result_preview: str


@dataclass
class DelegationStartData:
    child_id: str
    description: str
    role: str | None


@dataclass
class DelegationEndData:
    child_id: str
    status: str


@dataclass
class CompressionData:
    before: int
    after: int
    saved: int


@dataclass
class SafetyWarningData:
    warning_type: str
    iteration: int | None = None
    limit: int | None = None
    timeout_seconds: float | None = None
    tool_name: str | None = None
    repeated_count: int | None = None


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
