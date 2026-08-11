from __future__ import annotations

import asyncio
import json as _json
from typing import TYPE_CHECKING

from ..task import ActivityEvent, ActivityEventType, ReportPayload, TaskStatus
from .registry import ToolDef

if TYPE_CHECKING:
    from ...core.agent import Agent


TOOL_DELEGATE_DEF = ToolDef(
    name="delegate",
    description="Delegate a task to a sub-agent that handles it autonomously. "
                "The sub-agent sees ONLY your description, role, and optional "
                "system_prompt — nothing from your parent. "
                "Use system_prompt to override the sub-agent's default behavior. "
                "Returns the child's status, ID, report summary, "
                "artifact IDs, and confidence (if set). For failed children, "
                "returns the failure reason.",
    input_schema={
        "type": "object",
        "properties": {
            "description": {"type": "string", "description": "Description of the task for the sub-agent"},
            "role": {"type": "string", "description": "Optional role tag scoping the sub-agent's focus (e.g. 'You are a Security Auditor. Flag issues, do not fix them.')"},
            "system_prompt": {"type": "string", "description": "Optional custom system prompt for the sub-agent. Overrides the default agent behavior. Use for A/B testing different prompt strategies."},
        },
        "required": ["description"],
    },
)

TOOL_REPORT_DEF = ToolDef(
    name="report",
    description="Report final results to parent agent and complete this agent's work. "
                "Include a concrete summary of findings, artifact_ids referencing any "
                "files written, optionally a technical analysis and full report, and "
                "optionally a confidence score (0.0–1.0).",
    input_schema={
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "Summary of findings"},
            "artifact_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "IDs of artifacts to attach (referenced in earlier report/read_artifact output)",
            },
            "files_written": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Paths of files written to disk during this task",
            },
            "technical_summary": {
                "type": "string",
                "description": "Optional detailed technical analysis of findings",
            },
            "full_report": {
                "type": "string",
                "description": "Optional complete report with full detail",
            },
            "confidence": {
                "type": "number",
                "description": "Optional confidence score (0.0 = uncertain, 1.0 = certain)",
            },
        },
        "required": ["summary"],
    },
)

TOOL_ESCALATE_DEF = ToolDef(
    name="escalate",
    description="Escalate an issue to the parent agent",
    input_schema={
        "type": "object",
        "properties": {
            "issue": {"type": "string", "description": "Description of the issue"},
        },
        "required": ["issue"],
    },
)

TOOL_FAIL_DEF = ToolDef(
    name="fail",
    description="Report a failure and terminate this agent's work",
    input_schema={
        "type": "object",
        "properties": {
            "error": {"type": "string", "description": "Error message"},
        },
        "required": ["error"],
    },
)

TOOL_ASK_DEF = ToolDef(
    name="ask",
    description="Ask the user a question and get their response. Use when you need input, clarification, or confirmation.",
    input_schema={
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "The question to present to the user"},
        },
        "required": ["question"],
    },
)

TOOL_CONVERSE_DEF = ToolDef(
    name="converse",
    description="Send a message to another agent (by ID) and wait for its "
                "response. The target agent resumes with this new message "
                "appended to its existing context. Use this to continue a "
                "conversation with a child agent after it has reported, or "
                "to request follow-up work from a completed child agent.",
    input_schema={
        "type": "object",
        "properties": {
            "agent_id": {"type": "string", "description": "ID of the target agent (e.g. a child)"},
            "message": {"type": "string", "description": "Message or instruction for the target agent"},
        },
        "required": ["agent_id", "message"],
    },
)

TOOL_READ_ARTIFACT_DEF = ToolDef(
    name="read_artifact",
    description="Read an artifact by its ID. Artifacts are stored when agents call "
                "report(). Use this to look up a child agent's report contents by its "
                "artifact ID. Returns the artifact's headline and summary views.",
    input_schema={
        "type": "object",
        "properties": {
            "artifact_id": {"type": "string", "description": "The ID of the artifact to read"},
        },
        "required": ["artifact_id"],
    },
)


async def delegate(
    *, agent: Agent, description: str,
    role: str | None = None, system_prompt: str | None = None,
    _tool_call_id: str = "",
) -> str:
    child = agent.delegate(description, role=role, system_prompt=system_prompt)
    agent.emit_activity(ActivityEvent(
        agent_id=agent.id,
        event_type=ActivityEventType.DELEGATION_START,
        data={
            "child_id": child.id,
            "description": description[:200],
            "role": role,
        },
    ))
    task = asyncio.create_task(child.run())
    agent._runtime.track_agent_task(task)
    if agent._deferred_delegates is not None:
        agent._deferred_delegates.append((_tool_call_id, child, task))
        return _json.dumps({"child_id": child.id, "status": "pending"}, indent=2)

    await task
    return agent._format_delegate_result(child)


async def report(*, agent: Agent, summary: str, artifact_ids: list[str] | None = None, files_written: list[str] | None = None, confidence: float | None = None, technical_summary: str | None = None, full_report: str | None = None) -> str:
    agent.report(ReportPayload(
        task_id=agent.task.id,
        summary=summary,
        artifact_ids=artifact_ids or [],
        files_written=files_written or [],
        confidence=confidence,
        technical_summary=technical_summary,
        full_report=full_report,
    ))
    return f"Reported: {summary[:100]}"


async def escalate(*, agent: Agent, issue: str) -> str:
    agent.escalate(issue)
    return f"Escalated: {issue[:100]}"


async def fail(*, agent: Agent, error: str) -> str:
    agent.fail(error)
    return f"Failed: {error[:100]}"


async def ask(*, agent: Agent, question: str) -> str:
    loop = asyncio.get_event_loop()
    answer = await loop.run_in_executor(None, lambda: input(f"\n[Agent asks] {question}\nYour response: "))
    return answer.strip()


async def converse(*, agent: Agent, agent_id: str, message: str) -> str:
    target = agent.get_other_agent(agent_id)
    if not target:
        return f"Error: no agent found with ID {agent_id}"
    if target.task.status not in (TaskStatus.completed, TaskStatus.running):
        return (
            f"Error: agent {agent_id} status is "
            f"'{target.task.status.value}', cannot converse"
        )

    await target.continue_with_input(message)

    summary = ""
    for msg in reversed(target._messages or []):
        if msg.get("role") == "assistant" and msg.get("content"):
            summary = msg["content"][:500]
            break
    status = target.task.status.value
    return f"[Agent {agent_id[:8]}] {summary}\n(Status: {status})"


async def read_artifact(*, agent: Agent, artifact_id: str) -> str:
    artifact = agent._artifact_store.get(artifact_id)
    if not artifact:
        return f"Error: no artifact found with ID '{artifact_id}'"
    views = artifact.views
    parts = []
    for name in ("headline", "summary_200", "summary_1000", "technical", "full_report", "raw_data"):
        v = getattr(views, name, None)
        if v:
            parts.append(f"[{name}] {v}")
    return "\n".join(parts) if parts else f"Artifact {artifact_id} has no content."
