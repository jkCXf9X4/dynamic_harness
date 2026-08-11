from __future__ import annotations

import argparse
import asyncio
from typing import Any

from rich.style import Style
from rich.text import Text as RichText
from textual import events, on
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import RichLog, TextArea, Tree

from ..core.agent import Agent
from ..core.runner import AgentRunner
from ..core.runtime import Runtime
from ..core.task import ActivityEvent
from .common import build_runtime
from .present import AgentNode, build_agent_tree, build_stats
from .render import apply_tree, render_event, stats_lines

COMMANDS = {
    "/help": "Show this help message",
    "/history": "Show task history from this session",
    "/tree": "Show the full agent task graph",
    "/agents": "Show agent count and commit stats",
    "/reset": "Reset runtime (clear agents and task graph)",
    "/kill": "Kill the currently running agent immediately",
    "/new": "Start a fresh conversation (new root agent, preserves history)",
    "/verbose": "Show activity events (tool calls, delegations, LLM calls)",
    "/quiet": "Hide activity events \u2014 only show reports and failures",
    "exit": "Exit the TUI",
    "quit": "Exit the TUI",
}

STYLES: dict[str, Style] = {
    "output-label": Style(color="#888888"),
    "output-header": Style(bold=True, color="#00ff87"),
    "output-error": Style(color="#ff5555"),
    "output-event": Style(color="#55bbff"),
    "output-prompt": Style(bold=True, color="#ffffff"),
    "output-activity": Style(color="#8888aa", dim=True),
}

SEPARATOR = " " + "\u2500" * 40


def _render_text_tree(node: AgentNode, depth: int) -> list[str]:
    prefix = "  " * depth
    line = f"{prefix}{node.short_id} - {node.short_description} [{node.status}]"
    if node.usage:
        line += f" {node.usage}"
    lines = [line]
    for child in node.children:
        lines.extend(_render_text_tree(child, depth + 1))
    return lines


class PromptTextArea(TextArea):
    """TextArea where Enter submits and Ctrl+J inserts newlines."""

    class Submitted(Message):
        def __init__(self, text: str) -> None:
            self.text = text
            super().__init__()

    async def _on_key(self, event: events.Key) -> None:
        if event.key == "enter":
            if self.read_only:
                return
            event.stop()
            event.prevent_default()
            self.post_message(self.Submitted(self.text))
            self.clear()
            return
        await super()._on_key(event)


class TUI(App[None]):
    CSS = """
    Screen {
        layout: vertical;
    }

    Horizontal {
        height: 1fr;
    }

    Tree {
        width: 44;
        min-width: 44;
        border-right: solid #444;
        background: #1a1a2e;
        overflow-x: hidden;
    }

    Tree > .tree--label {
        padding: 0 1;
    }

    RichLog {
        height: 1fr;
        padding: 0 1;
        overflow-x: hidden;
    }

    TextArea {
        dock: bottom;
        height: auto;
        max-height: 12;
        margin: 0;
        padding: 0 2;
        border: none;
        background: #222244;
        color: #ffffff;
    }

    TextArea:focus {
        border: none;
    }
    """

    BINDINGS = [
        ("ctrl+c", "exit"),
        ("escape", "cancel"),
        ("page_up", "page_up"),
        ("page_down", "page_down"),
    ]

    def __init__(self, runtime: Runtime, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.runtime = runtime
        self._verbose: bool = True
        self._run_log: list[dict] = []
        self._current_agent_task: asyncio.Task | None = None
        self._root_agent: Agent | None = None
        self._tree_dirty: bool = False

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Tree("Agent Tree", id="sidebar")
            yield RichLog(id="output", max_lines=500, wrap=True, highlight=True)
        yield PromptTextArea(id="input", text="")

    def on_mount(self) -> None:
        self._wire_events()
        self.set_interval(0.5, self._maybe_refresh_tree)
        self._tree_dirty = True
        self._maybe_refresh_tree()
        self.query_one("#input", PromptTextArea).focus()

    def _wire_events(self) -> None:
        self.runtime.on_report(
            lambda aid, p: self._write_report(aid, p)
        )
        self.runtime.on_failure(
            lambda aid, f: self._write_failure(aid, f)
        )
        self.runtime.on_activity(
            lambda e: self._on_activity(e)
        )

    def write_output(self, style_name: str, text: str) -> None:
        style = STYLES.get(style_name, Style())
        self.query_one("#output", RichLog).write(RichText(text, style=style))

    def _write_report(self, aid: str, p: Any) -> None:
        self.write_output("output-event", f"\u2713 {aid[:8]} report done\n\n{p.summary}\n\n")
        self._tree_dirty = True

    def _write_failure(self, aid: str, f: Any) -> None:
        self.write_output("output-error", f"\u2717 {aid[:8]} fail: {f.error}\n")
        self._tree_dirty = True

    def _format_activity(self, event: ActivityEvent) -> str | None:
        text = render_event(event, emoji=True, show_args=True)
        if text is None:
            return None
        return text + "\n"

    def _on_activity(self, event: ActivityEvent) -> None:
        self._tree_dirty = True
        if not self._verbose:
            return
        text = self._format_activity(event)
        if text:
            self.write_output("output-activity", text)

    @on(PromptTextArea.Submitted)
    def on_prompt_submitted(self, event: PromptTextArea.Submitted) -> None:
        text = event.text.strip()
        if not text:
            return

        if text.lower() in ("exit", "quit"):
            self.action_exit()
            return

        self.write_output("output-prompt", f">>> {text}\n")

        if text.startswith("/"):
            asyncio.create_task(self._handle_command(text))
        else:
            asyncio.create_task(self._run_agent(text))

    async def _handle_command(self, text: str) -> None:
        cmd = text.strip().lower()

        if cmd == "/help":
            self.write_output("output-header", "Commands\n")
            for c, d in COMMANDS.items():
                self.write_output("output-label", f"  {c:<12} {d}\n")

        elif cmd == "/history":
            if not self._run_log:
                self.write_output("output-label", "No tasks yet.\n")
                return
            for i, entry in enumerate(self._run_log, 1):
                line = f"  {i}. {entry['task']} ({entry['agents']} agents, {entry['commits']} commits)"
                self.write_output("output-label", line + "\n")

        elif cmd == "/agents":
            stats = build_stats(self.runtime)
            self.write_output("output-label", f"Agents:  {stats.agents}\n")
            self.write_output("output-label", f"Commits: {stats.commits}\n")
            self.write_output("output-label", f"Tokens:  {stats.tokens}\n")

        elif cmd == "/reset":
            self.runtime.reset()
            self._root_agent = None
            self._run_log.clear()
            self._tree_dirty = True
            self.write_output("output-label", "Runtime reset.\n")

        elif cmd == "/new":
            self._root_agent = None
            self.write_output("output-label", "New conversation started.\n")

        elif cmd == "/kill":
            if self._current_agent_task and not self._current_agent_task.done():
                self._current_agent_task.cancel()
                self.write_output("output-error", "Agent task cancelled.\n")
            else:
                self.write_output("output-label", "No agent running.\n")

        elif cmd == "/verbose":
            self._verbose = True
            self.write_output("output-label", "Activity events shown.\n")

        elif cmd == "/quiet":
            self._verbose = False
            self.write_output("output-label", "Activity events hidden. Use /verbose to show.\n")

        elif cmd == "/tree":
            model = build_agent_tree(self.runtime)
            if not model:
                self.write_output("output-label", "No agents yet.\n")
                return
            for node in model:
                for line in _render_text_tree(node, 0):
                    self.write_output("output-label", line + "\n")

        else:
            self.write_output("output-error", f"Unknown command: {cmd}. Try /help\n")

    async def _run_agent(self, description: str) -> None:
        agent_count_before = self.runtime.agent_count()
        runner = AgentRunner(self.runtime)

        loop_task = asyncio.create_task(
            runner.run(
                description,
                root_agent=self._root_agent,
            )
        )
        self._current_agent_task = loop_task
        try:
            await loop_task
        except asyncio.CancelledError:
            self.write_output("output-error", "Agent run cancelled.\n")
        except Exception as e:
            self.write_output("output-error", f"Error: {e}\n")
        finally:

            self._current_agent_task = None
            if self._root_agent is None:
                agents = self.runtime.all_agents()
                first_id = next(iter(self.runtime.task_graph()), "")
                self._root_agent = self.runtime.get_agent(first_id) or (
                    next(iter(agents.values()), None)
                    if agents
                    else None
                )

        msg = f"\u2713 {self.runtime.repository.count()} commits, {self.runtime.agent_count()} agents"
        self.write_output("output-label", msg + "\n")
        self._tree_dirty = True

        self._run_log.append(
            {
                "task": description[:80],
                "agents": self.runtime.agent_count() - agent_count_before,
                "commits": self.runtime.repository.count(),
            }
        )

    def _maybe_refresh_tree(self) -> None:
        if not self._tree_dirty:
            return
        self._apply_tree()
        self._tree_dirty = False

    def _apply_tree(self) -> None:
        tree = self.query_one("#sidebar", Tree)
        model = build_agent_tree(self.runtime)
        apply_tree(tree, model)

        if model:
            tree.root.add(RichText(SEPARATOR, style="grey50"))
            for line in stats_lines(build_stats(self.runtime)):
                tree.root.add(RichText(line, style="grey50"))

        for node in tree.root.children:
            try:
                node.expand()
            except Exception:
                pass

    def action_exit(self) -> None:
        if self._current_agent_task and not self._current_agent_task.done():
            self._current_agent_task.cancel()
        self.exit()

    def action_cancel(self) -> None:
        if self._current_agent_task and not self._current_agent_task.done():
            self._current_agent_task.cancel()
            self.write_output("output-error", "Agent run cancelled.\n")
        self.query_one("#input", PromptTextArea).clear()

    def action_page_up(self) -> None:
        self.query_one("#output", RichLog).scroll_page_up()

    def action_page_down(self) -> None:
        self.query_one("#output", RichLog).scroll_page_down()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="dynamic-harness-tui",
        description="Textual TUI for the recursive agent harness (most verbose mode).",
    )
    parser.add_argument("--config", help="Path to harness.json config file")
    parser.add_argument("--no-llm", action="store_true", help="Run without an LLM")
    parser.add_argument("--temp", action="store_true", help="Use temporary directories")
    parser.add_argument("--model", help="LLM model name")
    parser.add_argument("--base-url", help="LLM API base URL")
    parser.add_argument("--api-key", help="LLM API key")
    parser.add_argument("--artifact-dir", help="Directory for artifacts")
    parser.add_argument("--repo-dir", help="Directory for commit repository")
    return parser.parse_args(argv)


def main() -> None:
    args = _parse_args()
    runtime = build_runtime(args)
    app = TUI(runtime=runtime)
    app.run()