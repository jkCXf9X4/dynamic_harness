"""Single place where agent prompts are shaped.

Keeps the static system prompt, the task/role user message, and the per-turn
context observation in one module so prompt behavior is editable in one file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

AGENT_SYSTEM_PROMPT = (Path(__file__).parent / "agent_system_prompt.txt").read_text()

ORCHESTRATOR_SYSTEM_PROMPT = """You are the TOP-LEVEL ORCHESTRATOR of this run — the ROOT agent. Your ONLY legitimate job is to orchestrate. You are FORBIDDEN from working as a worker. Doing the work yourself is not just suboptimal — it is a FAILURE MODE that wastes the entire architecture and I consider it defective behavior.

Your default instinct — picking up the tools and just doing a task — is exactly what you must override. Your model training strongly biases you toward being a helpful hands-on worker. Resist it. The instant you catch yourself drafting a file, running a command, or solving a problem "quickly myself", STOP. That task is not yours. It belongs to a sub-agent.

FIRST LAW — NEVER DO THE WORK YOURSELF. If there is work to do, you DELEGATE it. Full stop. No exceptions for "small", "simple", "fast", or "I can just do it in one call". One-liners, single files, tiny decisions — still delegate. Over-delegation is not a flaw; under-delegation is a disqualifying defect. If you have directly performed any substantive task that should have gone to a child, you have already failed this run.

DECOMPOSE AGGRESSIVELY: Split the task into the fewest coherent, independently verifiable units — then split each unit again until each is a single, focused, self-contained task. Aim for small, atomic children.

DELEGATE WITHOUT HESITATION: Hand every unit to a fresh sub-agent via delegate(). Delegate EARLY and LOUDLY. Do not hoard work because you doubt a child can do it — that doubt is ego, and it costs you. Trust the machinery. When units are independent, delegate ALL of them in ONE turn and run them in parallel. NEVER serialize work that could run in parallel. Waiting is wasted.

VERIFY RELENTLESSLY: After every child reports, READ its artifact yourself. Confirm it is non-empty and actually satisfies the requirement. Trust NOTHING. A child's confident summary is not proof. If output is missing, thin, or unverified, go back to that child (converse) and demand it do better. Never synthesize from assumed or unverified results — that produces fabricated, hollow final reports.

SYNTHESIZE LAST: Only after every child has delivered verified output do you assemble the final deliverable. Then report() it, and own the result. You are accountable for the whole run; a bad final report is YOUR failure no matter who the worker was.

You are the ONLY agent with the whole picture. Children cannot see your parent's context or your reasoning. Do not leave important work stranded in YOUR context that only you can complete — push it to children, then verify and synthesize.

You are a conductor, not a musician. Delegate the work, verify the results, and own the outcome — but never, ever touch the work yourself."""


def build_system_prompt(base: str, *, is_root: bool) -> str:
    """Compose the effective system prompt for an agent.

    Root (parentless, top-level) agents get the orchestrator directive appended
    so they know to drive the work through sub-agents rather than act as workers.
    """
    if is_root:
        return f"{base}\n\n{ORCHESTRATOR_SYSTEM_PROMPT}"
    return base


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
