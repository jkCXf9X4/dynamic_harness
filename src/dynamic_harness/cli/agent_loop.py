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
from ..core.capabilities import TOOL_ASK_DEF
from ..core.runtime import Runtime
from ..core.task import Task

if TYPE_CHECKING:
    from ..core.task import Failure, ReportPayload


def install_ask_tool(console: Console, runtime: Runtime) -> None:
    async def _ask(*, agent: Agent, question: str) -> str:
        console.print()
        answer = Prompt.ask(f"[bold cyan]Agent {agent.id[:8]} asks:[/] {question}")
        return answer.strip()
    runtime.tool_registry.register(TOOL_ASK_DEF, _ask)


class AgentLoop:
    def __init__(self, console: Console, runtime: Runtime) -> None:
        self.console = console
        self.runtime = runtime
        self.events: list[str] = []
        self.last_reports: list[tuple[str, str]] = []

    def connect(self) -> None:
        self.runtime.on_report(self._on_report)
        self.runtime.on_failure(self._on_failure)

    def _on_report(self, agent_id: str, payload: ReportPayload) -> None:
        tag = agent_id[:8]
        self.events.append(f"[bold green]\u2713[/] [dim]{tag}[/] report done")
        self.last_reports.append((tag, payload.summary))

    def _on_failure(self, agent_id: str, fail: Failure) -> None:
        tag = agent_id[:8]
        self.events.append(f"[bold red]\u2717[/] [dim]{tag}[/] fail: {fail.error}")

    def _make_tree(self, task_description_limit: int = 50) -> Tree:
        tree = Tree(":robot: [bold]Agent Tree[/]")
        g = self.runtime.task_graph()
        agents = self.runtime._agents

        def add_node(parent_id: str, parent_node: Tree) -> None:
            for child_id in g.get(parent_id, []):
                agent = agents.get(child_id)
                label = f"[dim]{child_id[:8]}[/]"
                if agent:
                    label += f" \u2014 {agent.task.description[:task_description_limit]}"
                    label += f"  [{agent.task.status.value}]"
                child_node = parent_node.add(label)
                add_node(child_id, child_node)

        for aid in g:
            agent = agents.get(aid)
            if agent and agent.parent is None:
                label = f"[bold]{aid[:8]}[/]"
                label += f" \u2014 {agent.task.description[:task_description_limit]}"
                label += f"  [{agent.task.status.value}]"
                node = tree.add(label)
                add_node(aid, node)

        return tree

    def _make_status(self) -> Table:
        table = Table.grid(padding=(0, 1))
        table.add_column()
        table.add_row(f"Agents: [bold]{self.runtime.agent_count()}[/]")
        table.add_row(f"Commits: [bold]{self.runtime.repository.count()}[/]")
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

    async def run(self, description: str, *, clear_events: bool = True, task_description_limit: int = 50) -> None:
        if clear_events:
            self.events.clear()

        root = self.runtime.spawn_agent(Task(description=description))

        with Live(self._render(), refresh_per_second=4, console=self.console) as live:
            root_task = asyncio.create_task(root.run())

            while not root_task.done():
                live.update(self._render())
                await asyncio.sleep(0.25)

            await root_task
            live.update(self._render())
