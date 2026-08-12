from __future__ import annotations

from typing import Any

from rich.tree import Tree as RichTree

from ..core.events_format import format_event
from ..core.task import ActivityEvent, TaskStatus
from .present import AgentNode, Stats

STATUS_COLORS: dict[str, str] = {
    TaskStatus.running.value: "yellow",
    TaskStatus.completed.value: "green",
    TaskStatus.failed.value: "red",
    TaskStatus.escalated.value: "orange3",
    TaskStatus.pending.value: "grey50",
}


def render_event(
    event: ActivityEvent,
    *,
    emoji: bool = False,
    show_args: bool = False,
) -> str | None:
    """Event -> text line (no trailing newline). Single source for the UI + logs."""
    return format_event(event, emoji=emoji, show_args=show_args)


def _status_color(status: str) -> str:
    return STATUS_COLORS.get(status, "grey50")


def render_rich_tree(model: list[AgentNode], title: str = "Agent Tree") -> RichTree:
    """Build a Rich Tree from AgentNode view-models."""
    tree = RichTree(f":robot: [bold]{title}[/]")
    for node in model:
        add_rich_node(tree, node)
    return tree


def add_rich_node(parent: RichTree, node: AgentNode) -> None:
    status = f"  [{_status_color(node.status)}]{node.status}[/]"
    label = f"[bold]{node.short_id}[/] \u2014 {node.short_description}{status}"
    if node.usage:
        label += f"[dim]{node.usage}[/]"
    child = parent.add(label)
    for kid in node.children:
        add_rich_node(child, kid)


def stats_lines(stats: Stats) -> list[str]:
    return [
        f" Agents: {stats.agents}",
        f" Commits: {stats.commits}",
        f" Tokens: {stats.tokens}",
    ]