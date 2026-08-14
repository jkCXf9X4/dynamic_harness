"""Single place where agent prompts are shaped.

Keeps the static system prompt, the task/role user message, and the per-turn
context observation in one module so prompt behavior is editable in one file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

AGENT_SYSTEM_PROMPT = (Path(__file__).parent / "agent_system_prompt.txt").read_text()


def build_user_message(description: str, role: str | None = None) -> str:
    """The initial user message an agent receives (task plus optional role scope)."""
    if role:
        return f"[ROLE] {role}\n\n[TASK] {description}"
    return description


@dataclass
class FocusLedger:
    """Mutable, runtime-held focus state re-stated to the agent each turn.

    This is separate from the (prompt-optimized) system prompt: the optimizer
    replaces ``agent_system_prompt.txt``, but reminders survive because they are
    rendered by code into the per-turn context observation, never baked into the
    optimizable prompt text.
    """

    objective: str = ""
    acceptance: list[str] = field(default_factory=list)
    deliverable: str = ""
    pending: list[str] = field(default_factory=list)
    done: list[str] = field(default_factory=list)
    # Show full acceptance/progress detail every N turns; re-state only
    # objective+deliverable in between so context stays flat.
    pulse_interval: int = 15


def render_focus(focus: FocusLedger, iteration: int) -> str:
    """Render the focus/reminder block with progressive pulsing.

    Full detail (objective, acceptance, remaining/done progress) is surfaced on
    the first turn and every ``pulse_interval`` turns; otherwise only the
    objective and deliverable are re-stated to keep the model anchored without
    unbounded context growth.
    """
    interval = focus.pulse_interval if focus.pulse_interval > 0 else 15
    show_full = iteration <= 1 or (iteration % interval) == 0

    lines: list[str] = []
    if focus.objective:
        lines.append(f"[Focus] Objective: {focus.objective}")
    if show_full:
        if focus.acceptance:
            lines.append("Acceptance: " + "; ".join(focus.acceptance))
        if focus.pending:
            lines.append("Remaining: " + "; ".join(focus.pending))
        if focus.done:
            lines.append("Done so far: " + "; ".join(focus.done))
    deliverable = focus.deliverable or (
        "write findings to disk via write() and call report() with "
        "artifact_ids / files_written"
    )
    lines.append(f"Deliverable: {deliverable}")
    return "\n".join(lines)


@dataclass
class ObservationInputs:
    iteration: int
    messages_count: int
    prompt_tokens: int
    # (prune_id, tool_names, estimated_tokens) for each active turn
    active_turns: Sequence[tuple[str, str, int]]
    next_turn_id: str
    environment_text: str
    task_description: str
    focus: FocusLedger | None = None


def build_observation(o: ObservationInputs) -> str:
    """The synthetic message shown to the model at the top of every turn."""
    if o.active_turns:
        turn_map = " · ".join(
            f"{pid}:{names}(~{est}tk)" for pid, names, est in o.active_turns
        )
        total_active = sum(est for _, _, est in o.active_turns)
    else:
        turn_map = "none"
        total_active = 0

    text = (
        f"[Context Observation]\n"
        f"Turn: {o.iteration}\n"
        f"Messages in context: {o.messages_count}\n"
        f"Estimated prompt tokens this agent: {o.prompt_tokens}\n"
        f"Active turn tokens: {total_active} (prune stale turns to cut this)\n"
        f"Recent committed turns (prune_id:tools~tokens): {turn_map}\n"
        f"Your next turn will commit as prune_id: {o.next_turn_id}.\n"
        f"Prune turns whose results are already on disk using "
        f"prune(prune_ids=['tN', ...]); the costliest turns save the most.\n"
        f"Your task: {o.task_description}\n"
        f"{o.environment_text}"
    )
    if o.focus:
        reminder = render_focus(o.focus, o.iteration)
        if reminder:
            text += "\n" + reminder
    return text
