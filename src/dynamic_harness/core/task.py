from __future__ import annotations

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
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class DelegateRequest(BaseModel):
    task: Task
    budget: int | None = None


class ReportPayload(BaseModel):
    task_id: str
    summary: str
    technical_summary: str | None = None
    full_report: str | None = None
    confidence: float | None = None
    claims: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    artifact_ids: list[str] = Field(default_factory=list)
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
