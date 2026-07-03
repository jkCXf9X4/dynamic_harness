from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from ..core.agent import Agent
from ..core.runner import AgentRunner
from ..core.capabilities import TOOL_ASK_DEF
from ..core.runtime import Runtime

if TYPE_CHECKING:
    from ..core.task import Failure, ReportPayload


def install_ask_tool(console: Console, runtime: Runtime) -> None:
    async def _ask(*, agent: Agent, question: str) -> str:
        console.print()
        answer = Prompt.ask(f"[bold cyan]Agent {agent.id[:8]} asks:[/] {question}")
        return answer.strip()
    runtime.tool_registry.register(TOOL_ASK_DEF, _ask)


class AgentLoop(AgentRunner):
    """Rich-rendering agent loop: a presentation layer over AgentRunner."""

    def __init__(self, console: Console, runtime: Runtime) -> None:
        super().__init__(runtime)
        self.console = console

    def _make_tree(self, task_description_limit: int = 50) -> Tree:
        tree = Tree(":robot: [bold]Agent Tree[/]")
        g = self.runtime.task_graph()
        agents = self.runtime._agents

        def usage_label(agent_id: str) -> str:
            u = self.runtime.get_usage(agent_id)
            t = u.get("total_tokens", 0)
            m = u.get("message_count", 0)
            if t or m:
                return f" [dim]({t}t, {m}msgs)[/]"
            return ""

        def add_node(parent_id: str, parent_node: Tree) -> None:
            for child_id in g.get(parent_id, []):
                agent = agents.get(child_id)
                label = f"[dim]{child_id[:8]}[/]"
                if agent:
                    label += f" \u2014 {agent.task.description[:task_description_limit]}"
                    label += f"  [{agent.task.status.value}]"
                    label += usage_label(child_id)
                child_node = parent_node.add(label)
                add_node(child_id, child_node)

        for aid in g:
            agent = agents.get(aid)
            if agent and agent.parent is None:
                label = f"[bold]{aid[:8]}[/]"
                label += f" \u2014 {agent.task.description[:task_description_limit]}"
                label += f"  [{agent.task.status.value}]"
                label += usage_label(aid)
                node = tree.add(label)
                add_node(aid, node)

        return tree

    def _make_status(self) -> Table:
        table = Table.grid(padding=(0, 1))
        table.add_column()
        usage = self.runtime.total_usage()
        table.add_row(f"Agents: [bold]{self.runtime.agent_count()}[/]")
        table.add_row(f"Commits: [bold]{self.runtime.repository.count()}[/]")
        table.add_row(f"Tokens: [bold]{usage['total_tokens']}[/]")
        return table

    def _make_events(self) -> Panel:
        lines = self.events[-8:]
        text = Text("\n".join(lines) if lines else "Waiting...")
        return Panel(text, title="Events", border_style="blue")

    def _render(self) -> Table:
        layout = Table.grid(padding=1)
        layout.add_column(ratio=1)
        row = Table.grid(padding=1)
        row.add_column(ratio=2)
        row.add_column(ratio=1)
        row.add_row(self._make_tree(), self._make_status())
        layout.add_row(row)
        layout.add_row(self._make_events())
        return layout

    async def run(self, description: str, *, clear_events: bool = True, task_description_limit: int = 50, shutdown_event: asyncio.Event | None = None, live_display: bool = True) -> None:
        if live_display:
            with Live(self._render, refresh_per_second=4, console=self.console) as live:
                await super().run(description, clear_events=clear_events, shutdown_event=shutdown_event, on_update=lambda: live.update(self._render()))
        else:
            await super().run(description, clear_events=clear_events, shutdown_event=shutdown_event)