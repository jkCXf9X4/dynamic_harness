from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, PrivateAttr, field_validator


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
    # Mission-command brief (3rd_party/agent_methods_and_tools/src/agent_methods/methods/mission-command/SKILL.md):
    # the parent states what + why + the boundaries, then leaves the how to the child.
    intent: str | None = None        # syfte/avsikt — why this task matters; the child's decision criterion
    end_state: str | None = None     # målbild — desired final condition ("what done looks like")
    constraints: list[str] = Field(default_factory=list)  # ramar — boundaries, limits, interface rules
    authority: str | None = None     # handlingsfrihet — license to adapt within the intent + report deviations
    # Model profile selected for this task (a name into config.profiles): the
    # agent runs on that profile's model instead of inheriting the runtime's.
    # None = inherit the runtime's active model.
    model_profile: str | None = None


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
    ASSISTANT_REPLY = "assistant_reply"
    INPUT_REQUEST = "input_request"
    INPUT_ANSWER = "input_answer"


class ActivityEvent(BaseModel):
    agent_id: str
    event_type: ActivityEventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data: dict[str, Any] = Field(default_factory=dict)


#: The kinds of external input a model may request mid-run (IMP-006).
INPUT_REQUEST_KINDS = ("clarification", "decision", "data", "capability")


class InputRequest(BaseModel):
    """A structured mid-run request for external input (IMP-006).

    Emitted by an agent via the ``request_input`` tool; rides the activity
    stream as an ``INPUT_REQUEST`` event and waits on the runtime's
    pending-request queue until an answer, the timeout policy, or a failure
    resolves it. An unanswered request never settles as pass.
    """

    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    kind: str = Field(default="clarification")

    _started_at: float = PrivateAttr(default=0.0)
    question: str
    options: list[str] = Field(default_factory=list)
    context_id: str | None = None
    timeout: float | None = Field(default=None, ge=0)
    default: str | None = None

    @field_validator("kind")
    @classmethod
    def _kind_known(cls, v: str) -> str:
        if v not in INPUT_REQUEST_KINDS:
            raise ValueError(f"kind must be one of {', '.join(INPUT_REQUEST_KINDS)}")
        return v


class InputAnswer(BaseModel):
    """An answer to a pending :class:`InputRequest`, routed back by id."""

    request_id: str
    value: str
    by: str = "operator"
    assumed: bool = False
