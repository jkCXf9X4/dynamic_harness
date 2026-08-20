from __future__ import annotations

import asyncio
import json
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
                "its own work (it cannot do hands-on work itself). "
                "Optionally set agent_type to a registered custom agent class "
                "name to instantiate a specialist sub-agent; unknown names are "
                "rejected. Returns the child's status, ID, report summary, "
                "artifact IDs, and confidence (if set). For failed children, "
                "returns the failure reason.",
    input_schema={
        "type": "object",
        "properties": {
            "description": {"type": "string", "description": "Description of the task for the sub-agent"},
            "role": {"type": "string", "description": "Optional role tag scoping the sub-agent's focus (e.g. 'You are a Security Auditor. Flag issues, do not fix them.'). Set role to 'orchestrator' to create a sub-orchestrator that must further decompose and delegate its own sub-tree — use when a delegated task is itself large enough to be split."},
            "system_prompt": {"type": "string", "description": "Optional custom system prompt for the sub-agent. Overrides the default agent behavior. Use for A/B testing different prompt strategies."},
            "agent_type": {"type": "string", "description": "Optional registered custom agent class name (via Runtime.register_agent_class) to instantiate for the sub-agent. Unknown names are rejected — the base Agent is never used as a silent fallback."},
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

TOOL_USAGE_DEF = ToolDef(
    name="usage",
    description="Read this agent's current message + token usage. Returns cumulative "
                "messages sent and prompt/completion/total tokens this run, your live "
                "in-context message count and token estimate, and the configured "
                "budget cap (if any). Call this when work is repetitive or growing — "
                "before the loop does, or to decide whether to delegate, prune, or "
                "compress. Cache-friendly: read your own counters instead of waiting "
                "for an injected per-turn observation.",
    input_schema={
        "type": "object",
        "properties": {},
        "required": [],
    },
)

TOOL_READ_ARTIFACT_DEF = ToolDef(
    name="read_artifact",
    description="Read an artifact by its ID (or by the agent id whose latest "
                "artifact is wanted). Progressive disclosure: by default returns "
                "only the cheap summary (headline + 200/1000-char summaries), "
                "preferring that slim preview over pulling the full body. Pass "
                "level='technical'|'full'|'raw' only when you actually need a "
                "deeper view. Pass file='<name>' to read a file the agent wrote "
                "(files_written), stored inside the artifact.",
    input_schema={
        "type": "object",
        "properties": {
            "artifact_id": {"type": "string", "description": "ID of the artifact, or of the agent whose latest artifact to read"},
            "file": {"type": "string", "description": "Optional: basename of a files_written file to read from the artifact's stored copy"},
            "level": {"type": "string", "description": "Disclosure level: auto (default, progressive summary), headline, summary, technical, full, raw"},
        },
        "required": ["artifact_id"],
    },
)

_VIEW_LEVELS: dict[str, tuple[str, ...]] = {
    "auto": ("headline", "summary_200", "summary_1000"),
    "headline": ("headline",),
    "summary": ("headline", "summary_200", "summary_1000"),
    "technical": ("technical",),
    "full": ("full_report",),
    "raw": ("raw_data",),
}


def _resolve_artifact(ctx: ToolContext, artifact_id: str):
    """Resolve an artifact by id; fall back to resolving a child *agent* id."""
    artifact = ctx.artifact_store.get(artifact_id)
    if not artifact:
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
    return artifact


async def read_artifact(
    *, ctx: ToolContext, artifact_id: str,
    file: str | None = None, level: str = "auto",
) -> str:
    artifact = _resolve_artifact(ctx, artifact_id)
    if not artifact:
        return f"Error: no artifact found with ID '{artifact_id}'"

    if file:
        content = ctx.artifact_store.read_text(artifact.id, file)
        if content is None:
            names = [p.name for p in ctx.artifact_store.list_files(artifact.id)]
            return (f"Error: artifact {artifact.id} has no stored file named '{file}'. "
                    f"Available: {', '.join(sorted(n for n in names if n != 'artifact.json')) or '(none)'}")
        return content

    level = (level or "auto").strip().lower()
    if level not in _VIEW_LEVELS:
        return (f"Error: unknown level '{level}'. One of: "
                f"{', '.join(_VIEW_LEVELS)}")
    names = _VIEW_LEVELS[level]

    parts: list[str] = []
    for name in names:
        v = getattr(artifact.views, name, None)
        if v:
            parts.append(f"[{name}] {v}")
    if not parts and level != "raw":
        # Progressive fallback: if the requested preview is empty but deeper
        # content exists (e.g. a prose-only report with a full_report), reveal
        # the first deeper view so the parent is not left empty-handed.
        for name in ("technical", "full_report", "raw_data"):
            v = getattr(artifact.views, name, None)
            if v:
                parts.append(f"[{name}] {v}")
                break
    if not parts:
        return f"Artifact {artifact.id} has no content at level '{level}'."

    body = "\n".join(parts)
    # For summary-level reads, hint at withheld detail so the parent can opt in.
    if level in ("auto", "summary", "headline"):
        deeper = [n for n in ("technical", "full_report", "raw_data")
                  if getattr(artifact.views, n, None)]
        if deeper:
            body += (f"\n\n[More detail available: {', '.join(deeper)}. "
                     f"Re-read with level='{deeper[0]}' to see it.]")
    return body


async def delegate(
    *, ctx: ToolContext, description: str,
    role: str | None = None, system_prompt: str | None = None,
    agent_type: str | None = None, _tool_call_id: str = "",
) -> str:
    return await ctx.run_delegate_tool(
        description, role=role, system_prompt=system_prompt,
        agent_type=agent_type, tool_call_id=_tool_call_id,
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


async def usage(*, ctx: ToolContext) -> str:
    return json.dumps(ctx.usage_summary(), indent=2)


async def read_artifact(*, ctx: ToolContext, artifact_id: str, file: str | None = None, level: str = "auto") -> str:
    artifact = _resolve_artifact(ctx, artifact_id)
    if not artifact:
        return f"Error: no artifact found with ID '{artifact_id}'"

    if file:
        content = ctx.artifact_store.read_text(artifact.id, file)
        if content is None:
            names = [p.name for p in ctx.artifact_store.list_files(artifact.id) if p.name != "artifact.json"]
            return (f"Error: no stored file named '{file}' for artifact {artifact.id}. "
                    f"Available: {', '.join(names) or '(none)'}")
        return content

    level = (level or "auto").strip().lower()
    if level not in _VIEW_LEVELS:
        return (f"Error: unknown level '{level}'. One of: {', '.join(_VIEW_LEVELS)}")
    names = _VIEW_LEVELS[level]

    parts: list[str] = []
    for name in names:
        v = getattr(artifact.views, name, None)
        if v:
            parts.append(f"[{name}] {v}")
    if not parts and level != "raw":
        for name in ("technical", "full_report", "raw_data"):
            v = getattr(artifact.views, name, None)
            if v:
                parts.append(f"[{name}] {v}")
                break
    if not parts:
        return f"Artifact {artifact.id} has no content at level '{level}'."

    body = "\n".join(parts)
    if level in ("auto", "headline", "summary"):
        deeper = [n for n in ("technical", "full_report", "raw_data")
                  if getattr(artifact.views, n, None)]
        if deeper:
            body += (f"\n\n[More detail available: {', '.join(deeper)}. "
                     f"Re-read with level='{deeper[0]}' to see it.]")
    return body
