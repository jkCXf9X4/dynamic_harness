from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from ..core.agent import Agent
from ..core.capabilities import TOOL_ASK_DEF
from ..core.runner import AgentRunner
from ..core.runtime import Runtime
from ..core.task import ActivityEvent
from .common import build_runtime, workspace_dir
from .format_event import format_event

console = Console()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="dynamic-harness",
        description="Direct terminal mode for the recursive agent harness.",
    )
    parser.add_argument("prompt", nargs="*", help="Task description (inline)")
    parser.add_argument("-m", metavar="FILE", help="Read task prompt from file")
    parser.add_argument("--config", help="Path to harness.json config file")
    parser.add_argument("--no-llm", action="store_true", help="Run without an LLM")
    parser.add_argument("--temp", action="store_true", help="Use temporary directories")
    parser.add_argument("--model", help="LLM model name")
    parser.add_argument("--base-url", help="LLM API base URL")
    parser.add_argument("--api-key", help="LLM API key")
    parser.add_argument("--artifact-dir", help="Directory for artifacts")
    parser.add_argument("--repo-dir", help="Directory for commit repository")
    parser.add_argument("--tui", action="store_true", help="Launch the Textual TUI instead")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive REPL mode")
    return parser.parse_args(argv)


def _install_ask_tool(runtime: Runtime) -> None:
    async def _ask(*, agent: Agent, question: str) -> str:
        console.print()
        answer = Prompt.ask(f"[bold cyan]Agent {agent.id[:8]} asks:[/] {question}")
        return answer.strip()
    runtime.tool_registry.register(TOOL_ASK_DEF, _ask)


def _format_event(event: ActivityEvent) -> str | None:
    return format_event(event)


def _make_tree(runtime: Runtime) -> Tree:
    tree = Tree(":robot: [bold]Agent Tree[/]")
    g = runtime.task_graph()
    agents = runtime.all_agents()

    def ul(id_: str) -> str:
        u = runtime.get_usage(id_)
        t = u.get("total_tokens", 0)
        m = u.get("message_count", 0)
        return f" [dim]({t}t, {m}msgs)[/]" if t or m else ""

    def add(parent_id: str, node: Tree) -> None:
        for cid in g.get(parent_id, []):
            a = agents.get(cid)
            lbl = f"[dim]{cid[:8]}[/]"
            if a:
                lbl += f" \u2014 {a.task.description[:50]}  [{a.task.status.value}]{ul(cid)}"
            n = node.add(lbl)
            add(cid, n)

    for aid in g:
        a = agents.get(aid)
        if a and a.parent is None:
            lbl = f"[bold]{aid[:8]}[/] \u2014 {a.task.description[:50]}  [{a.task.status.value}]{ul(aid)}"
            n = tree.add(lbl)
            add(aid, n)

    return tree


def _make_status(runtime: Runtime) -> Table:
    t = Table.grid(padding=(0, 1))
    t.add_column()
    u = runtime.total_usage()
    t.add_row(f"Agents: [bold]{runtime.agent_count()}[/]")
    t.add_row(f"Commits: [bold]{runtime.repository.count()}[/]")
    t.add_row(f"Tokens: [bold]{u['total_tokens']}[/]")
    return t


def _render(runtime: Runtime, events: list[str]) -> Table:
    layout = Table.grid(padding=1)
    layout.add_column(ratio=1)
    row = Table.grid(padding=1)
    row.add_column(ratio=2)
    row.add_column(ratio=1)
    row.add_row(_make_tree(runtime), _make_status(runtime))
    layout.add_row(row)
    lines = events[-8:]
    text = Text("\n".join(lines) if lines else "Waiting...")
    layout.add_row(Panel(text, title="Events", border_style="blue"))
    return layout


async def _run_with_live(runtime: Runtime, runner: AgentRunner, description: str, root_agent: Agent | None = None) -> None:
    runtime.event_bus.clear()

    events: list[str] = []
    runtime.on_report(lambda aid, p: events.append(f"\u2713 {aid[:8]} report done"))
    runtime.on_failure(lambda aid, f: events.append(f"\u2717 {aid[:8]} fail: {f.error[:60]}"))
    runtime.on_activity(lambda e: events.append(_format_event(e)) if _format_event(e) else None)

    with Live(_render, refresh_per_second=4, console=console) as live:
        run_task = asyncio.create_task(runner.run(description, root_agent=root_agent))
        while not run_task.done():
            live.update(_render(runtime, events))
            await asyncio.sleep(0.25)
        await run_task
        live.update(_render(runtime, events))


def _run_batch(runtime: Runtime, prompt: str) -> None:
    _install_ask_tool(runtime)
    runner = AgentRunner(runtime)
    asyncio.run(_run_with_live(runtime, runner, prompt))

    for tag, summary in runner.last_reports:
        console.print(f"\n[bold green]\u2713 Agent {tag}[/]")
        console.print(f"  {summary}\n")

    usage = runtime.total_usage()
    console.print(f"[dim]Agents: {runtime.agent_count()} | Commits: {runtime.repository.count()} | Tokens: {usage['total_tokens']}[/]")


async def _run_interactive_async(runtime: Runtime) -> None:
    _install_ask_tool(runtime)
    console.print("[bold]Dynamic Harness \u2014 Interactive Terminal[/]")
    console.print("Type a task, or /help for commands.\n")

    root_agent: Agent | None = None
    runner = AgentRunner(runtime)

    while True:
        try:
            text = Prompt.ask("[bold]>>>[/]")
        except (EOFError, KeyboardInterrupt):
            console.print()
            break

        text = text.strip()
        if not text:
            continue
        if text.lower() in ("exit", "quit"):
            break
        if text.startswith("/"):
            cmd = text.strip().lower()
            if cmd == "/help":
                console.print("[bold]Commands:[/]  /help  /agents  /reset  exit/quit")
            elif cmd == "/agents":
                u = runtime.total_usage()
                console.print(f"Agents: {runtime.agent_count()}  Commits: {runtime.repository.count()}  Tokens: {u['total_tokens']}")
            elif cmd == "/reset":
                runtime.reset()
                root_agent = None
                runner = AgentRunner(runtime)
                console.print("Runtime reset.")
            else:
                console.print(f"Unknown: {cmd}. Try /help")
            continue

        await _run_with_live(runtime, runner, text, root_agent=root_agent)

        if root_agent is None:
            first_id = next(iter(runtime.task_graph()), "")
            root_agent = runtime.get_agent(first_id)

        for tag, summary in runner.last_reports:
            console.print(f"\n[bold green]\u2713 Agent {tag}[/]")
            console.print(f"  {summary}\n")


def main() -> None:
    args = _parse_args()

    if args.tui:
        from .tui import main as tui_main
        tui_main()
        return

    runtime = build_runtime(args)

    if args.m:
        _run_batch(runtime, Path(args.m).read_text())
    elif args.prompt:
        _run_batch(runtime, " ".join(args.prompt))
    else:
        asyncio.run(_run_interactive_async(runtime))


if __name__ == "__main__":
    main()