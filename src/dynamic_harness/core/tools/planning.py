from __future__ import annotations

from typing import TYPE_CHECKING

from .registry import ToolDef

if TYPE_CHECKING:
    from ...core.tool_context import ToolContext


TOOL_PLAN_DEF = ToolDef(
    name="plan",
    description="Plan before executing: decompose your task into atomic, ordered "
                "steps and record them (PRIORITY). The plan is re-stated to you "
                "each turn as your remaining progress, and persisted to your "
                "checkpoint so an interrupted run can resume. Call this once at "
                "the start, before doing work. Mark optional objective/acceptance "
                "/deliverable to tighten the plan.",
    input_schema={
        "type": "object",
        "properties": {
            "steps": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Ordered atomic steps that complete the task",
            },
            "objective": {
                "type": "string",
                "description": "One-sentence restatement of the goal",
            },
            "acceptance": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Verifiable acceptance criteria for done",
            },
            "deliverable": {
                "type": "string",
                "description": "What artifact/file this plan must produce",
            },
        },
        "required": ["steps"],
    },
)

TOOL_CHECKPOINT_DEF = ToolDef(
    name="checkpoint",
    description="Persist your current progress to disk as structured JSON "
                "with a milestone note. Do this after each major step (e.g. after "
                "writing a file or finishing a sub-analysis) so the task can be "
                "resumed from this point if aborted or failed. Your plan and all "
                "prior turns are saved automatically; this records an explicit "
                "milestone marker that is surfaced again on resume, and "
                "guarantees durability now. Pass the plan step(s) just completed "
                "via ``done`` so your progress ledger advances and resume does "
                "not re-make finished work.",
    input_schema={
        "type": "object",
        "properties": {
            "note": {
                "type": "string",
                "description": "Short note describing what was completed at this milestone",
            },
            "done": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional exact plan step(s) completed at this milestone (must match plan() step text)",
            },
        },
        "required": ["note"],
    },
)


async def plan(
    *,
    ctx: ToolContext,
    steps: list[str],
    objective: str | None = None,
    acceptance: list[str] | None = None,
    deliverable: str | None = None,
) -> str:
    return ctx.set_plan(
        steps=steps,
        objective=objective,
        acceptance=acceptance,
        deliverable=deliverable,
    )


async def checkpoint(*, ctx: ToolContext, note: str, done: list[str] | None = None) -> str:
    return ctx.checkpoint(note, done=done)