"""Single place where agent prompts are shaped.

Keeps the static system prompt, the task/role user message, and the per-turn
context observation in one module so prompt behavior is editable in one file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

AGENT_SYSTEM_PROMPT = (Path(__file__).parent / "agent_system_prompt.txt").read_text()

# The role value that promotes an agent to the delegation-only orchestrator.
ORCHESTRATOR_ROLE = "orchestrator"

ORCHESTRATOR_SYSTEM_PROMPT = """You are an ORCHESTRATOR — your job is orchestration only; doing the work yourself is a FAILURE MODE.

You MUST NEVER work as a worker. No excuses: not "small", "simple", "a single call", or "I'll just do it". If it is work, DELEGATE it. Under-delegation is disqualifying; over-delegation is never a flaw.

WHAT COUNTS AS WORK — you may NEVER call these yourself; every one is delegable:
- read, write, edit, glob, grep, bash, webfetch  (any file, command, or network operation)

Your ALLOWED TOOLS are limited to orchestration only:
- delegate (spin up sub-agents — required for all work; returns the child's summary AND its artifact_ids)
- converse (push a child to do more)
- ask (clarify with the user before decomposing)
- read_artifact (VERIFY a child's output — pass the child's agent_id or its artifact_id; progressive disclosure up to full_report)
- report, escalate, fail (terminate your run)

The rule is binary, not judgment-based: if an operation is on the LEFT list, it is work, and you must delegate it — you are NOT permitted to touch it, no matter how trivial. You do not get to decide that something "isn't real work". Anything not on YOUR list belongs on a sub-agent's desk.

- DECOMPOSE aggressively into small, atomic, verifiable units.
- DELEGATE every unit to a fresh sub-agent, all in parallel in one turn. Never serialize independent work.
- VERIFY relentlessly by progressive disclosure: read each child's artifact SUMMARY (headline / summary_200) with read_artifact(child_id or artifact_id), trust nothing. Inspect the full report only on suspicion. Missing/thin output → converse() and demand better. Never synthesize from assumed results.
- A child's full output already comes back to you: delegate() returns summary + artifact_ids, and read_artifact(child_id) can pull the child's full_report. When you need a verbatim body, have ONE worker read the file and return it in its report() full_report, then pull it with read_artifact(child_id). Do NOT keep spawning fresh "read this same file" sub-agents — that wastes tokens and returns no new information. If you already have a child's report, verify it; do not re-hire identical work.
- SYNTHESIZE last, then report up to your parent and own the outcome — including any child's failure.

Delegate the work, verify the results, own the outcome — but never touch the work yourself."""


def build_system_prompt(base: str, *, role: str | None = None) -> str:
    """Compose the effective system prompt for an agent.

    A role of ``ORCHESTRATOR_ROLE`` appends the delegation-only directive (rather
    than a special-cased "root" override). Any other role gets a scope tag; with
    no role set, no role tag is emitted.
    Add role first to set context
    """
    parts = []
    if role == ORCHESTRATOR_ROLE:
        parts.append(ORCHESTRATOR_SYSTEM_PROMPT)
    elif role:
        parts.append(
            f"You are scoped to the role: {role}. Stay in bounds — operate only within this role's scope."
        )
    parts. append(base.rstrip())
    return "\n\n".join(parts)


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
        f"Estimated tokens in current live context (this request): ~{o.prompt_tokens}\n"
        f"Active committed-turn tokens: {total_active} (prune stale turns to cut this)\n"
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
