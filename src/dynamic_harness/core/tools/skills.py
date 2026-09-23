from __future__ import annotations

from typing import TYPE_CHECKING

from .registry import ToolDef

if TYPE_CHECKING:
    from ...core.tool_context import ToolContext


TOOL_SKILL_LOAD_DEF = ToolDef(
    name="skill_load",
    description="Load a named skill's full instructions into your context. "
                "Skills are task-specific instruction packages; their triggers "
                "(name + description) are listed in your environment's [Skills] "
                "block. Call this when one of those triggers applies to your "
                "task. Load each skill once — repeated identical loads are "
                "wasteful. Returns the skill body.",
    input_schema={
        "type": "object",
        "properties": {
            "skill": {"type": "string", "description": "The skill's name (the label in the [Skills] block)"},
        },
        "required": ["skill"],
    },
)


async def skill_load(*, ctx: ToolContext, skill: str) -> str:
    """Return the full instructions of the named skill, or a refusal.

    The body is read from the reference library root (already a read-only
    sandbox root, so no new path grants are needed). A skill scoped to roles
    the agent does not hold is refused — the role gate applies to loading, not
    just to the trigger index.
    """
    registry = getattr(ctx, "skills", None)
    if registry is None:
        return "Error: no skill library is available in this runtime."
    skill_obj = registry.get(skill)
    if skill_obj is None:
        available = ", ".join(registry.names()) or "(none)"
        return f"Error: unknown skill '{skill}'. Available skills: {available}"
    if not skill_obj.applies_to_role(ctx.role):
        scope = ", ".join(skill_obj.roles) or "(any)"
        return (
            f"status: refused\n"
            f"Skill '{skill}' is scoped to role(s) {scope} and is not loadable by "
            f"your role ({ctx.role or 'none'})."
        )
    body = skill_obj.body()
    if not body:
        return f"Error: skill '{skill}' is empty or unreadable."
    if skill_obj.dir:
        prefix = (
            f"[skill resources] This skill's directory is: {skill_obj.dir}\n"
            f"Resource files (templates, references) live here; read them with the "
            f"read() tool by absolute path.\n\n"
        )
        body = prefix + body
    return body