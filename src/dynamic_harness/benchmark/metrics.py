"""Per-(prompt, task) run metrics schema and capture.

This module defines the objective, comparable metrics captured for a single
benchmark run (one prompt applied to one task), and a collector that derives
them from a Runtime after the run completes.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RunMetrics:
    """Objective measurements for a single (prompt, task) benchmark run.

    All fields are comparable across runs. ``correct`` is the only *failable*
    signal: it is set by an external ground-truth verifier, not by the agent.
    """

    prompt_id: str = ""
    task_id: str = ""

    status: str = "completed"            # completed | failed | escalated
    correct: bool | None = None          # ground-truth verification result
    verification_note: str = ""

    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0

    agent_count: int = 1                # including root
    max_depth: int = 0                  # 0 = root only (no delegation)
    delegations: int = 0                # number of child agents spawned
    message_count: int = 0              # sum of messages across all agents
    total_turns: int = 0                # sum of LLM iterations across all agents
    llm_retries: int = 0                # total retried LLM calls across all agents
    failures: int = 0                   # number of failed agents
    escalations: int = 0                # number of escalated agents

    latency_s: float = 0.0             # wall-clock for the root run

    # Raw aggregate snapshot for debugging / transparency.
    extra: dict = field(default_factory=dict)

    @property
    def cost_per_1k(self) -> float:
        return self.cost_usd * 1000.0

    @property
    def tokens_per_agent(self) -> float:
        return self.total_tokens / max(1, self.agent_count)

    @property
    def passed(self) -> bool:
        return self.status == "completed" and self.correct is True


def _tree_depth(agent_id: str, graph: dict[str, list[str]]) -> int:
    """Max depth below ``agent_id`` in the task graph (0 for a leaf)."""
    children = graph.get(agent_id, [])
    if not children:
        return 0
    return 1 + max(_tree_depth(c, graph) for c in children)


class MetricsCollector:
    """Derive RunMetrics from a finished Runtime + verification result."""

    def __init__(self, *, price_input_per_mtok: float = 0.0, price_output_per_mtok: float = 0.0) -> None:
        self._price_in = price_input_per_mtok
        self._price_out = price_output_per_mtok

    def collect(
        self,
        runtime,
        *,
        root_agent_id: str,
        prompt_id: str,
        task_id: str,
        correct: bool | None,
        verification_note: str = "",
        latency_s: float = 0.0,
        status: str = "completed",
    ) -> RunMetrics:
        usage = runtime.total_usage()
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        agents = runtime.all_agents()
        graph = runtime.task_graph()

        max_depth = 0
        delegations = 0
        message_count = 0
        total_turns = 0
        llm_retries = 0
        failures = 0
        escalations = 0

        for aid, agent in agents.items():
            if agent.parent is not None:
                delegations += 1
            message_count += len(agent._messages)
            total_turns += agent._iteration
            llm_retries += agent._llm_retries
            st = agent.task.status.value if agent.task.status else ""
            if st == "failed":
                failures += 1
            elif st == "escalated":
                escalations += 1

        max_depth = _tree_depth(root_agent_id, graph)

        cost = (
            prompt_tokens * self._price_in / 1_000_000
            + completion_tokens * self._price_out / 1_000_000
        )

        return RunMetrics(
            prompt_id=prompt_id,
            task_id=task_id,
            status=status,
            correct=correct,
            verification_note=verification_note,
            total_tokens=usage.get("total_tokens", 0),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost,
            agent_count=len(agents),
            max_depth=max_depth,
            delegations=delegations,
            message_count=message_count,
            total_turns=total_turns,
            llm_retries=llm_retries,
            failures=failures,
            escalations=escalations,
            latency_s=latency_s,
        )
