from __future__ import annotations

import argparse
import asyncio
import os
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from dotenv import load_dotenv
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
from ..llm.openai_provider import OpenAIProvider

if TYPE_CHECKING:
    from ..core.task import ReportPayload


class AgentCLI:
    """Interactive CLI for running agents with live feedback."""

    def __init__(self, runtime: Runtime | None = None, llm: OpenAIProvider | None = None) -> None:
        self.console = Console()
        self.runtime = runtime
        self._llm = llm
        self._events: list[str] = []
        self._last_reports: list[tuple[str, str]] = []

    def _on_report(self, agent_id: str, payload: ReportPayload) -> None:
        tag = agent_id[:8]
        self._events.append(f"[bold green]✓[/] [dim]{tag}[/] report done")
        self._last_reports.append((tag, payload.summary))

    def _on_failure(self, agent_id: str, fail: ReportPayload) -> None:
        tag = agent_id[:8]
        self._events.append(f"[bold red]✗[/] [dim]{tag}[/] fail: {fail.error}")

    def _make_tree(self) -> Tree:
        tree = Tree(":robot: [bold]Agent Tree[/]")
        g = self.runtime.task_graph()
        agents = self.runtime._agents

        def add_node(parent_id: str, parent_node: Tree) -> None:
            for child_id in g.get(parent_id, []):
                agent = agents.get(child_id)
                label = f"[dim]{child_id[:8]}[/]"
                if agent:
                    label += f" — {agent.task.description[:50]}"
                    label += f"  [{agent.task.status.value}]"
                child_node = parent_node.add(label)
                add_node(child_id, child_node)

        for aid in g:
            agent = agents.get(aid)
            if agent and agent.parent is None:
                label = f"[bold]{aid[:8]}[/]"
                label += f" — {agent.task.description[:50]}"
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
        lines = self._events[-8:]
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

    def _build_runtime(self, args: argparse.Namespace) -> Runtime:
        artifact_root = Path(args.artifact_dir) if args.artifact_dir else Path(tempfile.mkdtemp())
        repo_root = Path(args.repo_dir) if args.repo_dir else Path(tempfile.mkdtemp())
        rt = Runtime(artifact_root=artifact_root, repo_root=repo_root)
        rt.on_report(self._on_report)
        rt.on_failure(self._on_failure)

        if not args.no_llm:
            load_dotenv()
            api_key = args.api_key or os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
            if api_key:
                model = args.model or os.environ.get("LLM_MODEL", "deepseek/deepseek-v4-flash")
                base_url = args.base_url or os.environ.get("LLM_BASE_URL", "https://openrouter.ai/api/v1")
                llm = OpenAIProvider(model=model, base_url=base_url, api_key=api_key, verify_ssl=False)
                rt.set_llm(llm)
        return rt

    def _install_ask_tool(self) -> None:
        async def _cli_ask(*, agent: Agent, question: str) -> str:
            self.console.print()
            answer = Prompt.ask(f"[bold cyan]Agent {agent.id[:8]} asks:[/] {question}")
            return answer.strip()
        self.runtime.tool_registry.register(TOOL_ASK_DEF, _cli_ask)

    async def run(self, description: str, args: argparse.Namespace | None = None) -> None:
        if self.runtime is None:
            args = args or _parse_args([description])
            self.runtime = self._build_runtime(args)
        self._install_ask_tool()

        self.console.print(f"\n[bold]Starting agent:[/] {description}\n", style="cyan")

        root = self.runtime.spawn_agent(Task(description=description))

        with Live(self._render(), refresh_per_second=4, console=self.console) as live:
            root_task = asyncio.create_task(root.run())

            while not root_task.done():
                live.update(self._render())
                await asyncio.sleep(0.25)

            await root_task
            live.update(self._render())

        for tag, summary in self._last_reports:
            if summary:
                self.console.print(Panel(summary, title=f"[bold green]Report from {tag}[/]", border_style="green"))
        self._last_reports.clear()
        self.console.print(f"\n[bold green]Done.[/] {self.runtime.agent_count()} agents, {self.runtime.repository.count()} commits\n")
        self._print_summary()

    def _print_summary(self) -> None:
        self.console.rule("Task Graph")
        for pid, kids in self.runtime.task_graph().items():
            agent = self.runtime.get_agent(pid)
            desc = f" [{agent.task.description[:60]}]" if agent else ""
            self.console.print(f"  [bold]{pid[:8]}[/]{desc}")
            for cid in kids:
                ca = self.runtime.get_agent(cid)
                desc = f" [{ca.task.description[:60]}]" if ca else ""
                self.console.print(f"    └── [dim]{cid[:8]}[/]{desc}")
        self.console.rule()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="dynamic-harness",
        description="Recursive agent harness — agents use tools, spawn sub-agents, and report results.",
    )
    parser.add_argument("task", nargs="*", default=[], help="Task description for the root agent")
    parser.add_argument("--no-llm", action="store_true", help="Run without an LLM (agent reports immediately)")
    parser.add_argument("--model", help="LLM model name (default: from LLM_MODEL env or deepseek/deepseek-v4-flash)")
    parser.add_argument("--base-url", help="LLM API base URL (default: from LLM_BASE_URL env or https://openrouter.ai/api/v1)")
    parser.add_argument("--api-key", help="LLM API key (default: from OPENROUTER_API_KEY or OPENAI_API_KEY env)")
    parser.add_argument("--artifact-dir", help="Directory for artifacts (default: temp dir)")
    parser.add_argument("--repo-dir", help="Directory for commit repository (default: temp dir)")
    parsed = parser.parse_args(argv)
    if not parsed.task:
        parsed.task = ["Explore", "the", "current", "directory", "structure", "and", "report", "what", "you", "find"]
    return parsed


async def run_agent(
    description: str,
    runtime: Runtime | None = None,
    llm: OpenAIProvider | None = None,
    args: argparse.Namespace | None = None,
) -> None:
    cli = AgentCLI(runtime=runtime, llm=llm)
    await cli.run(description, args=args)


def main() -> None:
    args = _parse_args()
    description = " ".join(args.task)
    cli = AgentCLI()
    asyncio.run(cli.run(description, args=args))


if __name__ == "__main__":
    main()