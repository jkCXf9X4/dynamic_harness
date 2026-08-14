from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    escalated = "escalated"


class Task(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    description: str
    role: str | None = None
    system_prompt: str | None = None
    parent_id: str | None = None
    status: TaskStatus = TaskStatus.pending
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), validate_default=True)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReportPayload(BaseModel):
    task_id: str
    summary: str
    technical_summary: str | None = None
    full_report: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    claims: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    artifact_ids: list[str] = Field(default_factory=list)
    files_written: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)


class BudgetRequest(BaseModel):
    task_id: str
    current_usage: int
    requested: int
    reason: str


class Escalation(BaseModel):
    task_id: str
    issue: str
    context: dict[str, Any] = Field(default_factory=dict)


class Failure(BaseModel):
    task_id: str
    error: str
    trace: str | None = None


@dataclass
class AgentOutcome:
    """Public, read-only summary of how an agent's run ended.

    Consumers (Runtime.run callers, MetricsCollector, delegation formatting)
    read this instead of reaching into private agent fields.
    """

    report: ReportPayload | None = None
    failure: Failure | None = None
    escalation: Escalation | None = None

    @property
    def is_terminal(self) -> bool:
        return (
            self.report is not None
            or self.failure is not None
            or self.escalation is not None
        )


class ActivityEventType(str, Enum):
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_END = "tool_call_end"
    LLM_CALL_START = "llm_call_start"
    LLM_CALL_END = "llm_call_end"
    DELEGATION_START = "delegation_start"
    DELEGATION_END = "delegation_end"
    COMPRESSION = "compression"
    SAFETY_WARNING = "safety_warning"
    SELF_HEAL = "self_heal"
    ITERATION = "iteration"


class ActivityEvent(BaseModel):
    agent_id: str
    event_type: ActivityEventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data: dict[str, Any] = Field(default_factory=dict)
