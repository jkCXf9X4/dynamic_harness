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

    async def run(
        self,
        description: str,
        *,
        clear_events: bool = True,
        task_description_limit: int = 50,
        shutdown_event: asyncio.Event | None = None,
        live_display: bool = True,
    ) -> None:
        async def _run_inner() -> None:
            await super().run(description, clear_events=clear_events)

        if live_display:
            with Live(self._render, refresh_per_second=4, console=self.console) as live:
                run_task = asyncio.create_task(_run_inner())
                while not run_task.done():
                    if shutdown_event and shutdown_event.is_set():
                        run_task.cancel()
                        break
                    live.update(self._render())
                    await asyncio.sleep(0.25)
                await run_task
        elif shutdown_event:
            run_task = asyncio.create_task(_run_inner())
            shutdown_task = asyncio.create_task(shutdown_event.wait())
            done, pending = await asyncio.wait(
                [run_task, shutdown_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            if shutdown_task in done:
                run_task.cancel()
            await run_task
        else:
            await _run_inner()