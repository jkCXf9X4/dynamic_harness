from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Any

from rich.style import Style
from rich.text import Text as RichText
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, RichLog, Tree

from ..core.agent import Agent
from ..core.runner import AgentRunner
from ..core.runtime import Runtime
from ..core.task import ActivityEvent, ActivityEventType
from .common import build_runtime, workspace_dir

COMMANDS = {
    "/help": "Show this help message",
    "/history": "Show task history from this session",
    "/tree": "Show the full agent task graph",
    "/agents": "Show agent count and commit stats",
    "/reset": "Reset runtime (clear agents and task graph)",
    "/kill": "Kill the currently running agent immediately",
    "/new": "Start a fresh conversation (new root agent, preserves history)",
    "/verbose": "Show activity events (tool calls, delegations, LLM calls)",
    "/quiet": "Hide activity events — only show reports and failures",
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

STATUS_COLORS = {
    "running": "yellow",
    "completed": "green",
    "failed": "red",
    "escalated": "orange3",
    "pending": "grey50",
}


def _fmt_usage(usage: dict) -> str:
    t = usage.get("total_tokens", 0)
    m = usage.get("message_count", 0)
    parts = []
    if t:
        parts.append(f"{t}t")
    if m:
        parts.append(f"{m}msgs")
    return f" ({', '.join(parts)})" if parts else ""


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

    Input {
        dock: bottom;
        height: 3;
        margin: 0;
        padding: 0 2;
        border: none;
        background: #222244;
        color: #ffffff;
    }

    Input:focus {
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

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Tree("Agent Tree", id="sidebar")
            yield RichLog(id="output", max_lines=500, wrap=True, highlight=True)
        yield Input(id="input", placeholder="Enter a task or /help for commands...")

    def on_mount(self) -> None:
        self.set_interval(0.5, self._refresh)
        self.query_one("#input", Input).focus()

    def write_output(self, style_name: str, text: str) -> None:
        style = STYLES.get(style_name, Style())
        self.query_one("#output", RichLog).write(RichText(text, style=style))

    def _format_activity(self, event: ActivityEvent) -> str | None:
        eid = event.agent_id[:8]
        d = event.data
        et = event.event_type

        if et == ActivityEventType.TOOL_CALL_START:
            name = d.get("tool_name", "?")
            args = d.get("arguments", {})
            arg_str = ", ".join(f"{k}={str(v)[:30]}" for k, v in args.items())
            return f"  [{eid}] 🔧 {name}({arg_str})\n"
        elif et == ActivityEventType.TOOL_CALL_END:
            name = d.get("tool_name", "?")
            rlen = d.get("result_length", 0)
            return f"  [{eid}] ✅ {name} → {rlen} bytes\n"
        elif et == ActivityEventType.LLM_CALL_END:
            tc = d.get("tool_calls", [])
            pt = d.get("prompt_tokens", 0)
            ct = d.get("completion_tokens", 0)
            tc_str = ", ".join(tc) if tc else "text-only"
            return f"  [{eid}] 💬 LLM → {tc_str} ({pt}+{ct} tokens)\n"
        elif et == ActivityEventType.DELEGATION_START:
            child = d.get("child_id", "?")[:8]
            desc = (d.get("description", "") or "")[:60]
            return f"  [{eid}] 👶 delegate → {child} \"{desc}\"\n"
        elif et == ActivityEventType.DELEGATION_END:
            child = d.get("child_id", "?")[:8]
            status = d.get("status", "?")
            return f"  [{eid}] 👶 {child} → {status}\n"
        elif et == ActivityEventType.COMPRESSION:
            before = d.get("before", 0)
            after = d.get("after", 0)
            saved = d.get("saved", 0)
            return f"  [{eid}] 🔄 compressed {before}→{after} msgs (-{saved})\n"
        elif et == ActivityEventType.SAFETY_WARNING:
            wtype = d.get("warning_type", "")
            if wtype == "max_iterations":
                return f"  [{eid}] ⚠️ max iterations ({d.get('iteration', 0)}/{d.get('limit', 0)})\n"
            return f"  [{eid}] ⚠️ repeated calls ({d.get('tool_name', '?')} x{d.get('repeated_count', 0)})\n"
        elif et == ActivityEventType.ITERATION:
            return None

    def _on_activity(self, event: ActivityEvent) -> None:
        if not self._verbose:
            return
        text = self._format_activity(event)
        if text:
            self.write_output("output-activity", text)

    @on(Input.Submitted, "#input")
    async def on_input(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return

        input_w = self.query_one("#input", Input)
        input_w.clear()

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
            total = self.runtime.total_usage()
            self.write_output("output-label", f"Agents:  {self.runtime.agent_count()}\n")
            self.write_output("output-label", f"Commits: {self.runtime.repository.count()}\n")
            self.write_output("output-label", f"Tokens:  {total['total_tokens']}\n")

        elif cmd == "/reset":
            self.runtime.reset()
            self._root_agent = None
            self._run_log.clear()
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
            g = self.runtime.task_graph()
            agents = self.runtime._agents
            if not g:
                self.write_output("output-label", "No agents yet.\n")
                return

            def render_node(aid: str, depth: int) -> None:
                agent = agents.get(aid)
                prefix = "  " * depth
                if agent:
                    label = f"{prefix}{aid[:8]} - {agent.task.description[:50]} [{agent.task.status.value}]"
                    usage = self.runtime.get_usage(aid)
                    ustr = _fmt_usage(usage)
                    if ustr:
                        label += f" {ustr}"
                    self.write_output("output-label", label + "\n")
                for child in g.get(aid, []):
                    render_node(child, depth + 1)

            for aid in g:
                agent = agents.get(aid)
                if agent and agent.parent is None:
                    render_node(aid, 0)

        else:
            self.write_output("output-error", f"Unknown command: {cmd}. Try /help\n")

    async def _run_agent(self, description: str) -> None:
        agent_count_before = self.runtime.agent_count()
        runner = AgentRunner(self.runtime)

        self.runtime.on_report(
            lambda aid, p: self.write_output(
                "output-event", f"\u2713 {aid[:8]} report done\n\n{p.summary}\n\n"
            )
        )
        self.runtime.on_failure(
            lambda aid, f: self.write_output(
                "output-error", f"\u2717 {aid[:8]} fail: {f.error}\n"
            )
        )

        self.runtime.on_activity(
            lambda e: self._on_activity(e)
        )

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
                first_id = next(iter(self.runtime.task_graph()), "")
                self._root_agent = self.runtime.get_agent(first_id) or (
                    self.runtime._agents.get(next(iter(self.runtime._agents), ""))
                    if self.runtime._agents
                    else None
                )

        msg = f"\u2713 {self.runtime.repository.count()} commits, {self.runtime.agent_count()} agents"
        self.write_output("output-label", msg + "\n")

        self._run_log.append(
            {
                "task": description[:80],
                "agents": self.runtime.agent_count() - agent_count_before,
                "commits": self.runtime.repository.count(),
            }
        )

    def _refresh(self) -> None:
        self._update_tree()

    def _update_tree(self) -> None:
        tree = self.query_one("#sidebar", Tree)
        tree.clear()

        g = self.runtime.task_graph()
        agents = self.runtime._agents

        if not g:
            tree.root.add(RichText(" No agents yet.", style="grey50"))
            tree.root.add(RichText(" Enter a task to begin.", style="grey50"))
            return

        def add_children(parent_id: str, parent_node: Any) -> None:
            for child_id in g.get(parent_id, []):
                agent = agents.get(child_id)
                if agent:
                    status = agent.task.status.value
                    color = STATUS_COLORS.get(status, "grey50")
                    label = RichText.assemble(
                        (f"  {agent.id[:8]}  ", "bold"),
                        (agent.task.description[:40], ""),
                        (f" [{status}]", color),
                    )
                    usage = self.runtime.get_usage(child_id)
                    ustr = _fmt_usage(usage)
                    if ustr:
                        label.append(ustr, "grey50")
                    child_node = parent_node.add(label)
                    add_children(child_id, child_node)
                else:
                    parent_node.add(RichText(f"  {child_id[:8]}", style="dim"))
                    add_children(child_id, parent_node)

        for aid in g:
            agent = agents.get(aid)
            if agent and agent.parent is None:
                status = agent.task.status.value
                color = STATUS_COLORS.get(status, "grey50")
                label = RichText.assemble(
                    (f"  {agent.id[:8]}  ", "bold"),
                    (agent.task.description[:46], ""),
                    (f" [{status}]", color),
                )
                usage = self.runtime.get_usage(aid)
                ustr = _fmt_usage(usage)
                if ustr:
                    label.append(ustr, "grey50")
                node = tree.root.add(label)
                add_children(aid, node)

        total = self.runtime.total_usage()
        tree.root.add(RichText(" " + "\u2500" * 40, style="grey50"))
        tree.root.add(RichText(f" Agents: {self.runtime.agent_count()}", style="grey50"))
        tree.root.add(RichText(f" Commits: {self.runtime.repository.count()}", style="grey50"))
        tree.root.add(RichText(f" Tokens: {total['total_tokens']}", style="grey50"))

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

    def action_page_up(self) -> None:
        self.query_one("#output", RichLog).scroll_page_up()

    def action_page_down(self) -> None:
        self.query_one("#output", RichLog).scroll_page_down()


def _build_runtime(args: argparse.Namespace) -> Runtime:
    return build_runtime(args)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="dynamic-harness",
        description="Interactive TUI for the recursive agent harness.",
    )
    parser.add_argument("-m", metavar="FILE", help="Read task prompt from file (bypasses TUI)")
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

    if args.m:
        prompt = Path(args.m).read_text()
        runner = AgentRunner(runtime)
        asyncio.run(runner.run(prompt))

        for tag, summary in runner.last_reports:
            print(f"\n=== Agent {tag} ===\n{summary}\n")

        usage = runtime.total_usage()
        print(f"Agents: {runtime.agent_count()} | Commits: {runtime.repository.count()} | Tokens: {usage['total_tokens']}")
        return

    app = TUI(runtime=runtime)
    app.run()


if __name__ == "__main__":
    main()