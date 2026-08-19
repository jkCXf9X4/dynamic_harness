from __future__ import annotations

import asyncio
import sys
from typing import TYPE_CHECKING

from ..task import ReportPayload, TaskStatus
from .registry import ToolDef

if TYPE_CHECKING:
    from ...core.tool_context import ToolContext


TOOL_DELEGATE_DEF = ToolDef(
    name="delegate",
    description="Delegate a task to a sub-agent that handles it autonomously. "
                "The sub-agent sees ONLY your description, role, and optional "
                "system_prompt — nothing from your parent. "
                "Use system_prompt to override the sub-agent's default behavior. "
                "Set role to 'orchestrator' to force deeper decomposition: the "
                "sub-agent becomes a sub-orchestrator that must split and delegate "
                "its own work (it cannot do hands-on work itself). Returns the "
                "child's status, ID, report summary, artifact IDs, and confidence "
                "(if set). For failed children, returns the failure reason.",
    input_schema={
        "type": "object",
        "properties": {
            "description": {"type": "string", "description": "Description of the task for the sub-agent"},
            "role": {"type": "string", "description": "Optional role tag scoping the sub-agent's focus (e.g. 'You are a Security Auditor. Flag issues, do not fix them.'). Set role to 'orchestrator' to create a sub-orchestrator that must further decompose and delegate its own sub-tree — use when an delegated task is itself large enough to be split."},
            "system_prompt": {"type": "string", "description": "Optional custom system prompt for the sub-agent. Overrides the default agent behavior. Use for A/B testing different prompt strategies."},
        },
        "required": ["description"],
    },
)

TOOL_REPORT_DEF = ToolDef(
    name="report",
    description="Report final results to parent agent and complete this agent's work. "
                "Include a concrete summary of findings, artifact_ids referencing any "
                "files written, optionally a technical analysis, a confidence score "
                "(0.0–1.0), and — critically — put any full body of content the parent "
                "must read verbatim (e.g. a file's complete contents) in full_report, "
                "NOT only in a file on disk. The parent reads full_report via "
                "read_artifact; content hidden only on disk may not reach it.",
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
    *, ctx: ToolContext, description: str,
    role: str | None = None, system_prompt: str | None = None,
    _tool_call_id: str = "",
) -> str:
    return await ctx.run_delegate_tool(
        description, role=role, system_prompt=system_prompt, tool_call_id=_tool_call_id,
    )


async def report(*, ctx: ToolContext, summary: str, artifact_ids: list[str] | None = None, files_written: list[str] | None = None, confidence: float | None = None, technical_summary: str | None = None, full_report: str | None = None) -> str:
    ctx.report(ReportPayload(
        task_id=ctx.task_id,
        summary=summary,
        artifact_ids=artifact_ids or [],
        files_written=files_written or [],
        confidence=confidence,
        technical_summary=technical_summary,
        full_report=full_report,
    ))
    return f"Reported: {summary[:100]}"


async def escalate(*, ctx: ToolContext, issue: str) -> str:
    ctx.escalate(issue)
    return f"Escalated: {issue[:100]}"


async def fail(*, ctx: ToolContext, error: str) -> str:
    ctx.fail(error)
    return f"Failed: {error[:100]}"


async def ask(*, ctx: ToolContext, question: str) -> str:
    if not sys.stdin.isatty():
        return (
            "NO_USER_AVAILABLE: running in non-interactive mode, no user to ask. "
            "Do NOT treat this as confirmation. Proceed using your best judgment "
            "or escalate if a human decision is genuinely required."
        )
    loop = asyncio.get_event_loop()
    answer = await loop.run_in_executor(None, lambda: input(f"\n[Agent asks] {question}\nYour response: "))
    return answer.strip()


async def converse(*, ctx: ToolContext, agent_id: str, message: str) -> str:
    target = ctx.get_other_agent(agent_id)
    if not target:
        return f"Error: no agent found with ID {agent_id}"
    if target.task.status not in (TaskStatus.completed, TaskStatus.running):
        return (
            f"Error: agent {agent_id} status is "
            f"'{target.task.status.value}', cannot converse"
        )

    await ctx.continue_with_input(agent_id, message)

    summary = ctx.latest_assistant_message(agent_id)
    status = target.task.status.value
    return f"[Agent {agent_id[:8]}] {summary}\n(Status: {status})"


async def read_artifact(*, ctx: ToolContext, artifact_id: str) -> str:
    artifact = ctx.artifact_store.get(artifact_id)
    if not artifact:
        # Fall back to resolving by *agent* id: parents only know their child's
        # agent id (from delegate), so read that agent's latest report artifact.
        agent = ctx.get_other_agent(artifact_id)
        if agent is not None:
            report_aid = getattr(agent, "_report_artifact_id", None)
            if report_aid:
                artifact = ctx.artifact_store.get(report_aid)
            if not artifact and getattr(agent, "last_report", None):
                for aid in (agent.last_report.artifact_ids or []):
                    candidate = ctx.artifact_store.get(aid)
                    if candidate is not None:
                        artifact = candidate
                        break
    if not artifact:
        return f"Error: no artifact found with ID '{artifact_id}'"
    views = artifact.views
    parts = []
    for name in ("headline", "summary_200", "summary_1000", "technical", "full_report", "raw_data"):
        v = getattr(views, name, None)
        if v:
            parts.append(f"[{name}] {v}")
    return "\n".join(parts) if parts else f"Artifact {artifact_id} has no content."
