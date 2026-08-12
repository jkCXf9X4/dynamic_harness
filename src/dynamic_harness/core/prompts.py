"""Single place where agent prompts are shaped.

Keeps the static system prompt, the task/role user message, and the per-turn
context observation in one module so prompt behavior is editable in one file.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

AGENT_SYSTEM_PROMPT = (Path(__file__).parent / "agent_system_prompt.txt").read_text()


def build_user_message(description: str, role: str | None = None) -> str:
    """The initial user message an agent receives (task plus optional role scope)."""
    if role:
        return f"[ROLE] {role}\n\n[TASK] {description}"
    return description


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

    return (
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
