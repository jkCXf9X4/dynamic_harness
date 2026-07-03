from __future__ import annotations

import argparse
import asyncio
import tempfile
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from ..core.runtime import Runtime
from .agent_loop import AgentLoop, install_ask_tool
from .common import build_runtime


COMMANDS = {
    "/help": "Show this help message",
    "/history": "Show task history from this session",
    "/tree": "Show the full agent task graph",
    "/agents": "Show agent count and commit stats",
    "/reset": "Reset runtime (clear agents and task graph)",
    "exit": "Exit the TUI",
    "quit": "Exit the TUI",
}

COMPLETER = WordCompleter(list(COMMANDS.keys()), ignore_case=True)


class TUI:
    """Interactive prompt that keeps the runtime alive across tasks."""

    def __init__(self, runtime: Runtime) -> None:
        self.runtime = runtime
        self.console = Console()
        self._run_log: list[dict] = []

        history_path = Path(tempfile.gettempdir()) / ".dynamic-harness-history"
        self.session = PromptSession[str](
            history=FileHistory(str(history_path)),
            completer=COMPLETER,
        )

        install_ask_tool(self.console, self.runtime)

    async def _handle_command(self, text: str) -> None:
        cmd = text.strip().lower()

        if cmd in ("exit", "quit"):
            raise StopIteration

        if cmd == "/help":
            self.console.print("\n[bold]Commands[/]")
            for cmd_text, desc in COMMANDS.items():
                self.console.print(f"  [cyan]{cmd_text:<12}[/] {desc}")
            self.console.print()

        elif cmd == "/history":
            if not self._run_log:
                self.console.print("[dim]No tasks yet.[/]")
                return
            table = Table(title="Task History", header_style="bold cyan")
            table.add_column("#", style="dim")
            table.add_column("Task")
            table.add_column("Agents", justify="right")
            table.add_column("Commits", justify="right")
            for i, entry in enumerate(self._run_log, 1):
                table.add_row(str(i), entry["task"], str(entry["agents"]), str(entry["commits"]))
            self.console.print(table)

        elif cmd == "/tree":
            tree = Tree(":robot: [bold]Agent Tree[/]")
            g = self.runtime.task_graph()
            agents = self.runtime._agents

            def add_node(parent_id: str, parent_node: Tree) -> None:
                for child_id in g.get(parent_id, []):
                    agent = agents.get(child_id)
                    label = f"[dim]{child_id[:8]}[/]"
                    if agent:
                        label += f" \u2014 {agent.task.description[:60]}"
                        if agent.task.status.value != "completed":
                            label += f"  [[{agent.task.status.value}]]"
                    child_node = parent_node.add(label)
                    add_node(child_id, child_node)

            roots_shown = 0
            for aid in g:
                agent = agents.get(aid)
                if agent and agent.parent is None:
                    label = f"[bold]{aid[:8]}[/]"
                    label += f" \u2014 {agent.task.description[:60]}"
                    label += f"  [{agent.task.status.value}]"
                    node = tree.add(label)
                    add_node(aid, node)
                    roots_shown += 1

            if roots_shown == 0:
                self.console.print("[dim]No agents yet.[/]")
            else:
                self.console.print(tree)

        elif cmd == "/agents":
            stats = Table.grid(padding=(0, 2))
            stats.add_column()
            stats.add_row(f"Agents:  [bold]{self.runtime.agent_count()}[/]")
            stats.add_row(f"Commits: [bold]{self.runtime.repository.count()}[/]")
            stats.add_row(f"Tasks:   [bold]{len(self._run_log)}[/]")
            self.console.print(stats)

        elif cmd == "/reset":
            self.runtime.reset()
            self._run_log.clear()
            self.console.print("[yellow]Runtime reset.[/]")

        else:
            self.console.print(f"[red]Unknown command: {cmd}. Try /help[/]")

    async def _run_agent(self, description: str) -> None:
        loop = AgentLoop(self.console, self.runtime)
        loop.connect()
        await loop.run(description)

        for tag, summary in loop.last_reports:
            if summary:
                self.console.print(Panel(summary, title=f"[bold green]Report from {tag}[/]", border_style="green"))
        self.console.print(f"[bold green]\u2713[/] {self.runtime.repository.count()} commits, {self.runtime.agent_count()} agents\n")

    async def loop(self) -> None:
        self.console.print()
        self.console.rule("[bold]dynamic-harness TUI[/]")
        self.console.print("[dim]Type a task for the agent, or /help for commands.[/]")
        self.console.print()

        try:
            while True:
                try:
                    text = await self.session.prompt_async(">>> ")
                except (EOFError, KeyboardInterrupt):
                    self.console.print()
                    break

                text = text.strip()
                if not text:
                    continue
                if text.lower() in ("exit", "quit"):
                    break
                if text.startswith("/"):
                    await self._handle_command(text)
                    continue

                agent_count_before = self.runtime.agent_count()

                try:
                    await self._run_agent(text)
                except Exception as e:
                    self.console.print(f"[red]Error: {e}[/]")
                    continue

                self._run_log.append({
                    "task": text[:80],
                    "agents": self.runtime.agent_count() - agent_count_before,
                    "commits": self.runtime.repository.count(),
                })

        except StopIteration:
            pass

        self.console.rule("[bold]Goodbye[/]")
        self.console.print()


def _build_runtime(args: argparse.Namespace) -> Runtime:
    return build_runtime(args)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="dynamic-harness",
        description="Interactive TUI for the recursive agent harness.",
    )
    parser.add_argument("--no-llm", action="store_true", help="Run without an LLM")
    parser.add_argument("--temp", action="store_true", help="Use temporary directories (data lost between sessions)")
    parser.add_argument("--model", help="LLM model name")
    parser.add_argument("--base-url", help="LLM API base URL")
    parser.add_argument("--api-key", help="LLM API key")
    parser.add_argument("--artifact-dir", help="Directory for artifacts")
    parser.add_argument("--repo-dir", help="Directory for commit repository")
    return parser.parse_args(argv)


def main() -> None:
    args = _parse_args()
    runtime = _build_runtime(args)
    tui = TUI(runtime=runtime)
    asyncio.run(tui.loop())


if __name__ == "__main__":
    main()