from __future__ import annotations

import argparse
import asyncio
import signal
from collections import deque
from pathlib import Path
from typing import Any

from prompt_toolkit.application import Application
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, VSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import TextArea
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from ..core.runner import AgentRunner
from ..core.runtime import Runtime
from .common import build_runtime, workspace_dir


COMMANDS = {
    "/help": "Show this help message",
    "/history": "Show task history from this session",
    "/tree": "Show the full agent task graph",
    "/agents": "Show agent count and commit stats",
    "/reset": "Reset runtime (clear agents and task graph)",
    "/kill": "Kill the currently running agent immediately",
    "exit": "Exit the TUI",
    "quit": "Exit the TUI",
}

COMPLETER = WordCompleter(list(COMMANDS.keys()), ignore_case=True)

TREE_STYLE = Style([
    ("sidebar", "bg:#1a1a2e"),
    ("tree-header", "bold fg:#00ff87"),
    ("tree-running", "fg:#ffd700"),
    ("tree-completed", "fg:#00ff87"),
    ("tree-failed", "fg:#ff5555"),
    ("tree-escalated", "fg:#ffaa00"),
    ("tree-pending", "fg:#888888"),
    ("tree-dim", "fg:#555555"),
    ("tree-usage", "fg:#888888"),
    ("output-label", "fg:#888888"),
    ("output-header", "bold fg:#00ff87"),
    ("output-error", "fg:#ff5555"),
    ("output-event", "fg:#55bbff"),
    ("output-prompt", "bold"),
    ("input", "fg:#ffffff bg:#222244"),
    ("divider", "fg:#444444"),
])


def _fmt_usage(usage: dict) -> str:
    t = usage.get("total_tokens", 0)
    m = usage.get("message_count", 0)
    parts = []
    if t:
        parts.append(f"{t}t")
    if m:
        parts.append(f"{m}msgs")
    return f" ({', '.join(parts)})" if parts else ""


class TUI:
    """Interactive prompt with persistent agent tree sidebar."""

    def __init__(self, runtime: Runtime) -> None:
        self.runtime = runtime
        self.console = Console()
        self._run_log: list[dict] = []
        self._current_agent_task: asyncio.Task | None = None
        self._shutdown = asyncio.Event()
        self._output_lines: deque[tuple[str, str]] = deque(maxlen=500)

        self._app: Application[None] | None = None

        history_path = workspace_dir() / ".prompt-history"
        history_path.parent.mkdir(parents=True, exist_ok=True)

        # Wrap accept_handler so it is not a coroutine (TextArea expects sync or handles both)
        self._input_area = TextArea(
            height=1,
            style="class:input",
            multiline=False,
            accept_handler=self._on_input_accepted,
        )
        self._input_area.buffer.completer = COMPLETER
        self._input_area.buffer.history = FileHistory(str(history_path))

        self._tree_control = FormattedTextControl(self._get_tree_fragments)
        self._output_control = FormattedTextControl(self._get_output_fragments)

        tree_window = Window(
            content=self._tree_control,
            width=44,
            style="class:sidebar",
            wrap_lines=False,
        )
        output_window = Window(
            content=self._output_control,
            wrap_lines=True,
        )
        input_window = self._input_area.window

        body = VSplit([
            tree_window,
            Window(width=1, char="│", style="class:divider"),
            HSplit([output_window, input_window]),
        ])

        self._layout = Layout(body, focused_element=self._input_area)

        kb = KeyBindings()
        kb.add("c-c")(self._handle_exit)
        kb.add("escape")(self._handle_sigint)
        kb.add("c-d")(self._handle_eof)

        self._app = Application(
            layout=self._layout,
            key_bindings=kb,
            style=TREE_STYLE,
            full_screen=True,
            mouse_support=True,
        )

    def _write_output(self, style_class: str, text: str) -> None:
        self._output_lines.append((style_class, text))
        self._invalidate_app()

    def _invalidate_app(self) -> None:
        if self._app:
            self._app.invalidate()

    def _get_tree_fragments(self) -> list[tuple[str, str]]:
        result: list[tuple[str, str]] = [
            ("class:tree-header", " Agent Tree\n"),
            ("class:tree-dim", " " + "\u2500" * 40 + "\n"),
        ]
        g = self.runtime.task_graph()
        agents = self.runtime._agents

        if not g:
            result.append(("class:tree-pending", " No agents yet.\n"))
            result.append(("class:tree-dim", " Enter a task to begin.\n"))
            result.append(("class:tree-dim", " " + "\u2500" * 40 + "\n"))
            result.append(("class:tree-usage", " Agents: 0\n"))
            result.append(("class:tree-usage", " Commits: 0\n"))
            result.append(("class:tree-usage", " Tokens: 0\n"))
            return result

        def add_node(parent_id: str, depth: int) -> None:
            children = g.get(parent_id, [])
            for i, child_id in enumerate(children):
                agent = agents.get(child_id)
                is_last = i == len(children) - 1
                connector = "\u2514\u2500 " if is_last else "\u251c\u2500 "
                prefix = "  " * (depth - 1) + connector if depth > 0 else "  "
                if agent:
                    status = agent.task.status.value
                    style_map = {
                        "running": "class:tree-running",
                        "completed": "class:tree-completed",
                        "failed": "class:tree-failed",
                        "escalated": "class:tree-escalated",
                        "pending": "class:tree-pending",
                    }
                    s = style_map.get(status, "class:tree-dim")
                    label = f"{prefix}{agent.id[:8]} {agent.task.description[:32]}"
                    usage = self.runtime.get_usage(child_id)
                    ustr = _fmt_usage(usage)
                    result.append((s, f"{label} [{status}]{ustr}\n"))
                else:
                    result.append(("class:tree-dim", f"{prefix}{child_id[:8]}\n"))
                add_node(child_id, depth + 1)

        for aid in g:
            agent = agents.get(aid)
            if agent and agent.parent is None:
                status = agent.task.status.value
                style_map = {
                    "running": "class:tree-running",
                    "completed": "class:tree-completed",
                    "failed": "class:tree-failed",
                    "escalated": "class:tree-escalated",
                    "pending": "class:tree-pending",
                }
                s = style_map.get(status, "class:tree-dim")
                label = f" {agent.id[:8]} {agent.task.description[:38]}"
                usage = self.runtime.get_usage(aid)
                ustr = _fmt_usage(usage)
                result.append((s, f"{label} [{status}]{ustr}\n"))
                add_node(aid, 1)

        total = self.runtime.total_usage()
        result.append(("class:tree-dim", " " + "\u2500" * 40 + "\n"))
        result.append(("class:tree-usage", f" Agents: {self.runtime.agent_count()}\n"))
        result.append(("class:tree-usage", f" Commits: {self.runtime.repository.count()}\n"))
        result.append(("class:tree-usage", f" Tokens: {total['total_tokens']}\n"))
        return result

    def _get_output_fragments(self) -> list[tuple[str, str]]:
        return list(self._output_lines)

    def _on_input_accepted(self, buf: Any) -> bool:
        text = buf.text.strip()
        buf.text = ""
        if not text:
            return False
        if text.lower() in ("exit", "quit"):
            self._shutdown.set()
            if self._current_agent_task and not self._current_agent_task.done():
                self._current_agent_task.cancel()
            if self._app:
                self._app.exit()
            return True

        self._write_output("class:output-prompt", f">>> {text}\n")

        if text.startswith("/"):
            asyncio.create_task(self._run_in_background(self._handle_command(text)))
        else:
            asyncio.create_task(self._run_agent_async(text))
        return True

    async def _run_in_background(self, coro: Any) -> None:
        try:
            await coro
        except Exception as e:
            self._write_output("class:output-error", f"Error: {e}\n")

    def _handle_sigint(self, _event: object) -> None:
        if self._current_agent_task and not self._current_agent_task.done():
            self._current_agent_task.cancel()
            self._write_output("class:output-error", "Agent run cancelled.\n")

    def _handle_exit(self, _event: object) -> None:
        if self._current_agent_task and not self._current_agent_task.done():
            self._current_agent_task.cancel()
        self._shutdown.set()
        if self._app:
            self._app.exit()

    def _handle_eof(self, _event: object) -> None:
        self._shutdown.set()
        if self._app:
            self._app.exit()

    async def _handle_command(self, text: str) -> None:
        cmd = text.strip().lower()

        if cmd == "/help":
            self._write_output("class:output-header", "Commands\n")
            for cmd_text, desc in COMMANDS.items():
                self._write_output("class:output-label", f"  {cmd_text:<12} {desc}\n")

        elif cmd == "/history":
            if not self._run_log:
                self._write_output("class:output-label", "No tasks yet.\n")
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
                        usage = self.runtime.get_usage(child_id)
                        ustr = _fmt_usage(usage)
                        if ustr:
                            label += f"  [dim]{ustr}[/]"
                    child_node = parent_node.add(label)
                    add_node(child_id, child_node)

            roots_shown = 0
            for aid in g:
                agent = agents.get(aid)
                if agent and agent.parent is None:
                    label = f"[bold]{aid[:8]}[/]"
                    label += f" \u2014 {agent.task.description[:60]}"
                    label += f"  [{agent.task.status.value}]"
                    usage = self.runtime.get_usage(aid)
                    ustr = _fmt_usage(usage)
                    if ustr:
                        label += f"  [dim]{ustr}[/]"
                    node = tree.add(label)
                    add_node(aid, node)
                    roots_shown += 1

            if roots_shown == 0:
                self.console.print("[dim]No agents yet.[/]")
            else:
                self.console.print(tree)

        elif cmd == "/agents":
            total = self.runtime.total_usage()
            stats = Table.grid(padding=(0, 2))
            stats.add_column()
            stats.add_row(f"Agents:  [bold]{self.runtime.agent_count()}[/]")
            stats.add_row(f"Commits: [bold]{self.runtime.repository.count()}[/]")
            stats.add_row(f"Tasks:   [bold]{len(self._run_log)}[/]")
            stats.add_row(f"Tokens:  [bold]{total['total_tokens']}[/]")
            self.console.print(stats)

        elif cmd == "/reset":
            self.runtime.reset()
            self._run_log.clear()
            self._write_output("class:output-label", "Runtime reset.\n")

        elif cmd == "/kill":
            if self._current_agent_task and not self._current_agent_task.done():
                self._current_agent_task.cancel()
                self._write_output("class:output-error", "Agent task cancelled.\n")
            else:
                self._write_output("class:output-label", "No agent running.\n")

        else:
            self._write_output("class:output-error", f"Unknown command: {cmd}. Try /help\n")

    async def _run_agent_async(self, description: str) -> None:
        agent_count_before = self.runtime.agent_count()
        self._write_output("class:output-event", f"Running: {description}\n")

        runner = AgentRunner(self.runtime)
        runner.connect()

        self.runtime.on_report(lambda aid, p: self._write_output("class:output-event", f"\u2713 {aid[:8]} report done\n"))
        self.runtime.on_failure(lambda aid, f: self._write_output("class:output-error", f"\u2717 {aid[:8]} fail: {f.error}\n"))

        self._shutdown.clear()

        loop_task = asyncio.create_task(
            runner.run(description, shutdown_event=self._shutdown, on_update=self._invalidate_app)
        )
        self._current_agent_task = loop_task
        try:
            await loop_task
        except asyncio.CancelledError:
            self._write_output("class:output-error", "Agent run cancelled.\n")
        except Exception as e:
            self._write_output("class:output-error", f"Error: {e}\n")
        finally:
            self._current_agent_task = None

        for tag, summary in runner.last_reports:
            if summary:
                self.console.print(Panel(summary, title=f"[bold green]Report from {tag}[/]", border_style="green"))
        msg = f"\u2713 {self.runtime.repository.count()} commits, {self.runtime.agent_count()} agents"
        self._write_output("class:output-label", msg + "\n")

        self._run_log.append({
            "task": description[:80],
            "agents": self.runtime.agent_count() - agent_count_before,
            "commits": self.runtime.repository.count(),
        })

    async def _refresh_loop(self) -> None:
        while not self._shutdown.is_set():
            if self._app:
                self._app.invalidate()
            try:
                await asyncio.wait_for(self._shutdown.wait(), timeout=0.5)
            except asyncio.TimeoutError:
                pass

    async def loop(self) -> None:
        signal.signal(signal.SIGINT, lambda sig, frame: self._handle_exit(None))

        refresh_task = asyncio.create_task(self._refresh_loop())
        try:
            await self._app.run_async()
        finally:
            self._shutdown.set()
            refresh_task.cancel()
            try:
                await refresh_task
            except asyncio.CancelledError:
                pass
            self.console.print()
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