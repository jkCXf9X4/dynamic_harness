from __future__ import annotations

from dataclasses import dataclass, field

from ..core.runtime import Runtime

ID_CHARS = 8
TREE_DESC_CHARS = 40


def _clip(text: str, n: int) -> str:
    if len(text) <= n:
        return text
    return text[:n]


@dataclass
class AgentNode:
    """Tree node view-model: engine-agnostic representation of one agent."""

    agent_id: str
    description: str
    status: str
    tokens: int = 0
    messages: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    artifact_ids: list[str] = field(default_factory=list)
    trace_path: str | None = None
    children: list[AgentNode] = field(default_factory=list)

    @property
    def short_id(self) -> str:
        return _clip(self.agent_id, ID_CHARS)

    @property
    def short_description(self) -> str:
        return _clip(self.description, TREE_DESC_CHARS)

    @property
    def usage(self) -> str:
        if not (self.tokens or self.messages):
            return ""
        # Show the provider-billed breakdown so a cache-heavy prompt isn't
        # hidden behind a single inflated total: `prompt` is the FULL prompt
        # (cached portion included, billed alongside as `cached`).
        parts = []
        if self.prompt_tokens or self.completion_tokens:
            parts.append(f"{self.prompt_tokens}p")
            if self.completion_tokens:
                parts.append(f"{self.completion_tokens}c")
            if self.cached_tokens:
                parts.append(f"{self.cached_tokens}cr")
        elif self.tokens:
            parts.append(f"{self.tokens}t")
        if self.messages:
            parts.append(f"{self.messages}msgs")
        return f" ({', '.join(parts)})"


@dataclass
class Stats:
    agents: int = 0
    commits: int = 0
    tokens: int = 0


def build_agent_tree(runtime: Runtime) -> list[AgentNode]:
    """Walk runtime task graph into nested AgentNode view-models (roots only)."""
    g = runtime.task_graph()
    agents = runtime.all_agents()
    roots = [
        aid
        for aid in g
        if aid in agents and agents[aid].parent is None
    ]

    def build(aid: str) -> AgentNode:
        agent = agents[aid]
        usage = runtime.get_usage(aid)
        prov = runtime.provenance(agent.id)
        return AgentNode(
            agent_id=agent.id,
            description=agent.task.description,
            status=agent.task.status.value,
            tokens=usage.get("total_tokens", 0),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            cached_tokens=usage.get("cached_tokens", 0),
            messages=agent.message_count,
            artifact_ids=prov["artifact_ids"],
            trace_path=prov["trace_path"],
            children=[
                build(cid) for cid in g.get(aid, []) if cid in agents
            ],
        )

    return [build(aid) for aid in roots]


def build_stats(runtime: Runtime) -> Stats:
    total = runtime.total_usage()
    return Stats(
        agents=runtime.agent_count(),
        commits=runtime.repository.count(),
        tokens=total["total_tokens"],
    )


def render_text_tree(nodes: list[AgentNode]) -> str:
    """Plain-text agent tree for quick operator evaluation.

    One line per agent showing id, status, description, messages, and a
    compact token breakdown — enough to spot a stuck/looping agent without a
    live dashboard. Engine-agnostic (no terminal-library markup) so it can be
    persisted to disk.
    """
    if not nodes:
        return "(no agents)\n"

    lines: list[str] = []

    def walk(nodes: list[AgentNode], prefix: str, last: bool) -> None:
        for i, node in enumerate(nodes):
            is_last = i == len(nodes) - 1
            branch = "└" if is_last else "├"
            lines.append(
                f"{prefix}{branch} {node.short_id} [{node.status}] "
                f"{node.short_description}{node.usage}"
            )
            child_prefix = prefix + ("  " if is_last else "│ ")
            walk(node.children, child_prefix, is_last)

    walk(nodes, "", last=True)
    return "\n".join(lines) + "\n"