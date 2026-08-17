from __future__ import annotations

import argparse
import asyncio
import os
import sys
import termios
import tty
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from ..core.agent import Agent
from ..core.tools.agents import TOOL_ASK_DEF
from ..core.runtime import Runtime
from .common import build_runtime
from .present import build_agent_tree, build_stats
from .render import render_event, render_rich_tree

console = Console()

_HISTORY: list[str] = []


def _render_input(prompt: str, text: list[str], pos: int) -> None:
    """Redraw a multi-line editable prompt anchored at the saved cursor position."""
    text_str = "".join(text)
    lines = text_str.split("\n")
    before = text_str[:pos]
    line_idx = before.count("\n")
    col = len(before.split("\n")[-1]) + (len(prompt) if line_idx == 0 else 0) + 1

    sys.stdout.write("\x1b[?25l")      # hide cursor during redraw
    sys.stdout.write("\x1b[u\x1b[J")   # restore to anchor, clear from there down
    sys.stdout.write(prompt + lines[0])
    for extra in lines[1:]:
        sys.stdout.write("\r\n" + extra)
    up = (len(lines) - 1) - line_idx
    if up:
        sys.stdout.write(f"\x1b[{up}A")
    sys.stdout.write("\r")
    if col > 1:
        sys.stdout.write(f"\x1b[{col - 1}C")
    sys.stdout.write("\x1b[?25h")      # show cursor at edit position
    sys.stdout.flush()


def _utf8_char(fd: int, lead: int) -> str:
    if 0xC0 <= lead <= 0xDF:
        n = 1
    elif 0xE0 <= lead <= 0xEF:
        n = 2
    elif 0xF0 <= lead <= 0xF7:
        n = 3
    else:
        n = 0
    data = bytes([lead]) + os.read(fd, n)
    return data.decode("utf-8", "replace")


def _read_input(prompt: str) -> str:
    """Read a line (or multi-line via Ctrl+J) with arrow-key cursor editing."""
    if not sys.stdin.isatty():
        return input(prompt)

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    prompt = console.render_str(prompt).plain
    text: list[str] = []
    pos = 0
    saved = ""
    hist_nav: int | None = None
    try:
        tty.setraw(fd)
        sys.stdout.write("\r\n\x1b[s")
        _render_input(prompt, text, pos)
        while True:
            raw = os.read(fd, 1)
            if not raw:
                continue
            b = raw[0]
            if b == 0x0D:  # Enter -> submit
                sys.stdout.write("\r\n")
                break
            elif b == 0x03:  # Ctrl+C
                raise KeyboardInterrupt
            elif b == 0x04:  # Ctrl+D
                raise EOFError
            elif b == 0x0A:  # Ctrl+J -> new line
                text.insert(pos, "\n")
                pos += 1
                hist_nav = None
            elif b in (0x7F, 0x08):  # backspace
                if pos > 0:
                    del text[pos - 1]
                    pos -= 1
                hist_nav = None
            elif b == 0x1B:  # escape sequence
                seq = os.read(fd, 1)
                if not seq or seq[0] != 0x5B:  # expect '['
                    continue
                s2 = os.read(fd, 1)
                if not s2:
                    continue
                c = s2[0]
                if c == 0x41:  # up
                    if hist_nav is None:
                        saved = "".join(text)
                        hist_nav = len(_HISTORY)
                    if hist_nav > 0:
                        hist_nav -= 1
                        text[:] = list(_HISTORY[hist_nav])
                        pos = len(text)
                elif c == 0x42:  # down
                    if hist_nav is not None:
                        hist_nav += 1
                        if hist_nav >= len(_HISTORY):
                            hist_nav = None
                            text[:] = list(saved)
                        else:
                            text[:] = list(_HISTORY[hist_nav])
                        pos = len(text)
                elif c == 0x43:  # right
                    if pos < len(text):
                        pos += 1
                elif c == 0x44:  # left
                    if pos > 0:
                        pos -= 1
                elif c == 0x48:  # home
                    pos = 0
                elif c == 0x46:  # end
                    pos = len(text)
                elif c == 0x33:  # delete (3~)
                    os.read(fd, 1)
                    if pos < len(text):
                        del text[pos]
            elif b >= 0x80:
                text.insert(pos, _utf8_char(fd, b))
                pos += 1
                hist_nav = None
            else:
                text.insert(pos, chr(b))
                pos += 1
                hist_nav = None
            _render_input(prompt, text, pos)
    finally:
        sys.stdout.flush()
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return "".join(text)


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
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive REPL mode")
    return parser.parse_args(argv)


def _install_ask_tool(runtime: Runtime, ask_queue: asyncio.Queue[str] | None = None) -> None:
    async def _ask(*, ctx, question: str) -> str:
        if ask_queue is None:
            console.print()
            answer = Prompt.ask(f"[bold cyan]Agent {ctx.agent_id[:8]} asks:[/] {question}")
            return answer.strip()
        await ask_queue.put(question)
        return (await ask_queue.get()).strip()
    runtime.tool_registry.register(TOOL_ASK_DEF, _ask)


def _make_tree(runtime: Runtime) -> Tree:
    return render_rich_tree(build_agent_tree(runtime))


def _make_status(runtime: Runtime) -> Table:
    t = Table.grid(padding=(0, 1))
    t.add_column()
    stats = build_stats(runtime)
    t.add_row(f"Agents: [bold]{stats.agents}[/]")
    t.add_row(f"Commits: [bold]{stats.commits}[/]")
    t.add_row(f"Tokens: [bold]{stats.tokens}[/]")
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


async def _run_with_live(runtime: Runtime, description: str, root_agent: Agent | None = None) -> Agent:
    runtime.event_bus.clear()

    events: list[str] = []
    runtime.on_report(lambda aid, p: events.append(f"\u2713 {aid[:8]} report done"))
    runtime.on_failure(lambda aid, f: events.append(f"\u2717 {aid[:8]} fail: {f.error[:60]}"))
    runtime.on_activity(lambda e: events.append(render_event(e)) if render_event(e) else None)

    ask_queue: asyncio.Queue[str] = asyncio.Queue()
    _install_ask_tool(runtime, ask_queue)

    with Live(get_renderable=lambda: _render(runtime, events), refresh_per_second=4, console=console) as live:
        run_task = asyncio.create_task(runtime.run(description, root_agent=root_agent))
        while not run_task.done():
            while not ask_queue.empty():
                question: str = ask_queue.get_nowait()
                live.stop()
                console.print()
                Prompt.ask(f"[bold cyan]Agent asks:[/] {question}")
                live.start()
            await asyncio.sleep(0.25)
    root = await run_task
    return root


def _print_outcome(root: Agent) -> None:
    if root.last_report:
        console.print(f"\n[bold green]\u2713 Agent {root.id[:8]}[/]")
        console.print(f"  {root.last_report.summary}\n")
    elif root.last_failure:
        console.print(f"\n[bold red]\u2717 Agent {root.id[:8]}[/] failed: {root.last_failure.error[:200]}\n")


def _run_batch(runtime: Runtime, prompt: str) -> None:
    root = asyncio.run(_run_with_live(runtime, prompt))
    _print_outcome(root)

    usage = runtime.total_usage()
    console.print(f"[dim]Agents: {runtime.agent_count()} | Commits: {runtime.repository.count()} | Tokens: {usage['total_tokens']}[/]")


async def _run_interactive_async(runtime: Runtime) -> None:
    console.print("[bold]Dynamic Harness \u2014 Interactive Terminal[/]")
    console.print("Type a task, or /help for commands.\n")

    root_agent: Agent | None = None

    while True:
        try:
            text = _read_input("[bold]>>>[/]")
        except (EOFError, KeyboardInterrupt):
            console.print()
            break

        text = text.strip()
        if not text:
            continue
        _HISTORY.append(text)
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
                console.print("Runtime reset.")
            else:
                console.print(f"Unknown: {cmd}. Try /help")
            continue

        root = await _run_with_live(runtime, text, root_agent=root_agent)
        if root_agent is None:
            root_agent = root
        _print_outcome(root)


def main() -> None:
    args = _parse_args()

    runtime = build_runtime(args)

    if args.m:
        _run_batch(runtime, Path(args.m).read_text())
    elif args.prompt:
        _run_batch(runtime, " ".join(args.prompt))
    else:
        asyncio.run(_run_interactive_async(runtime))


if __name__ == "__main__":
    main()