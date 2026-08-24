from __future__ import annotations

import argparse
import asyncio
import os
import select
import sys
import termios
import tty
from collections.abc import Callable
from pathlib import Path

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from ..core.agent import Agent
from ..core.prompts import ORCHESTRATOR_ROLE
from ..core.task import ActivityEventType
from ..core.tools.agents import TOOL_ASK_DEF
from ..core.runtime import Runtime
from .common import build_runtime
from .present import build_agent_tree, render_text_tree
from .state import StateWriter, attach_events

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


def _is_word_char(ch: str) -> bool:
    return ch.isalnum() or ch == "_"


def _prev_word_start(text: list[str], pos: int) -> int:
    """Move pos to the start of the preceding word (readline-style backward-word)."""
    i = pos
    n = len(text)
    while i > 0 and not _is_word_char(text[i - 1]):
        i -= 1
    while i > 0 and _is_word_char(text[i - 1]):
        i -= 1
    return i


def _next_word_end(text: list[str], pos: int) -> int:
    """Move pos to the end of the next word (readline-style forward-word)."""
    i = pos
    n = len(text)
    while i < n and _is_word_char(text[i]):
        i += 1
    while i < n and not _is_word_char(text[i]):
        i += 1
    return i


def _read_input(prompt: str) -> str:
    """Read a line (or multi-line via Ctrl+J/paste) with arrow-key cursor editing.

    Bracketed paste is enabled up front so a pasted newline can never be
    mistaken for Enter: pasted bytes arrive wrapped in ``\\x1b[200~`` /
    ``\\x1b[201~`` and are inserted literally.
    """
    if not sys.stdin.isatty():
        return input(prompt)

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    prompt = console.render_str(prompt).plain
    text: list[str] = []
    pos = 0
    saved = ""
    hist_nav: int | None = None
    pasting = False
    try:
        tty.setraw(fd)
        sys.stdout.write("\r\n\x1b[s\x1b[?2004h")
        sys.stdout.flush()
        _render_input(prompt, text, pos)
        while True:
            raw = os.read(fd, 1)
            if not raw:
                continue
            b = raw[0]
            if b == 0x0D:  # Enter (submit) or pasted newline
                if pasting or select.select([fd], [], [], 0)[0]:
                    # A CR inside a paste, or one followed by more buffered
                    # input, is a line break -- never a submit.
                    text.insert(pos, "\n")
                    pos += 1
                    hist_nav = None
                else:
                    sys.stdout.write("\r\n")
                    break
            elif b == 0x03:  # Ctrl+C
                raise KeyboardInterrupt
            elif b == 0x04:  # Ctrl+D
                raise EOFError
            elif b == 0x0A:  # LF (Ctrl+J / pasted newline) -> new line
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
                csi = bytearray()
                while True:
                    s = os.read(fd, 1)
                    if not s:
                        break
                    byte = s[0]
                    # Full-text string (F): 200~/201~ bracketed paste, etc.
                    if byte == 0x7E and csi[:1] == b"2" and len(csi) >= 2:
                        tail = csi[1:]
                        if tail == b"00":
                            pasting = True
                        elif tail == b"01":
                            pasting = False
                        break
                    if 0x40 <= byte <= 0x7E:  # final byte of the CSI
                        csi.append(byte)
                        break
                    csi.append(byte)
                if not 0x40 <= (csi[-1] if csi else 0) <= 0x7E:
                    continue
                c = csi[-1]
                params = [int(p) if p else 0 for p in "".join(
                    chr(x) for x in csi[:-1]
                ).split(";")] or [0]
                ctrl = 5 in params or "5" in "".join(chr(x) for x in csi[:-1])
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
                elif c == 0x43:  # right (or Ctrl+Right = forward word)
                    if ctrl:
                        pos = _next_word_end(text, pos)
                    elif pos < len(text):
                        pos += 1
                    hist_nav = None
                elif c == 0x44:  # left (or Ctrl+Left = backward word)
                    if ctrl:
                        pos = _prev_word_start(text, pos)
                    elif pos > 0:
                        pos -= 1
                    hist_nav = None
                elif c == 0x48:  # home
                    pos = 0
                elif c == 0x46:  # end
                    pos = len(text)
                elif c == 0x7E:  # CSI ~ keypad sequences: 3~ delete, 1~/7~ home, 4~/8~ end
                    if params and params[0] == 3 and pos < len(text):
                        del text[pos]
                    elif params and params[0] in (1, 7):
                        pos = 0
                    elif params and params[0] in (4, 8):
                        pos = len(text)
                    hist_nav = None
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
        sys.stdout.write("\x1b[?2004l")
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
    parser.add_argument("--resume", metavar="AGENT_ID", help="Resume an interrupted/failed agent from its persisted checkpoint")
    return parser.parse_args(argv)


def _install_ask_tool(runtime: Runtime, ask_queue: asyncio.Queue[str]) -> None:
    async def _ask(*, ctx, question: str) -> str:
        await ask_queue.put(question)
        return (await ask_queue.get()).strip()
    runtime.tool_registry.register(TOOL_ASK_DEF, _ask)


def _make_writer(runtime: Runtime) -> StateWriter:
    """Persist overview files in the run root, next to artifacts/repo/traces."""
    return StateWriter(runtime.artifact_store.root.parent)


class _ProgressLine:
    """Single-line `\\r` token counter, refreshed on a background task.

    Each frame fully clears the line (`\\x1b[2K`) before rewriting, so a shorter
    token count or label never leaves residue behind. Written straight to
    stdout to avoid Rich's console buffering mangling the raw `\\r`.
    """

    def __init__(self, get_tokens: Callable[[], int]) -> None:
        self._get_tokens = get_tokens
        self._label = ""
        self._task: asyncio.Task[None] | None = None

    def _render(self) -> None:
        label = f" \u00b7 {self._label}" if self._label else ""
        sys.stdout.write(f"\r\x1b[2K{self._get_tokens()} tokens{label}")
        sys.stdout.flush()

    async def _refresh(self) -> None:
        try:
            while True:
                self._render()
                await asyncio.sleep(0.2)
        except asyncio.CancelledError:
            pass

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.ensure_future(self._refresh())

    def set_label(self, label: str) -> None:
        self._label = label

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None
        sys.stdout.write("\r\x1b[K")
        sys.stdout.flush()


def _progress_label(event) -> str:
    """Short single-line label for the token counter, from an ActivityEvent."""
    d = event.data
    et = event.event_type
    if et == ActivityEventType.TOOL_CALL_START:
        return f"{event.agent_id[:8]} \u2192 {d.get('tool_name', '?')}"
    if et == ActivityEventType.DELEGATION_START:
        child = d.get("child_id", "?")[:8]
        return f"delegate \u2192 {child} \"{(d.get('description', '') or '')[:40]}\""
    if et == ActivityEventType.COMPRESSION:
        return f"({event.agent_id[:8]}) compress ({d.get('saved', 0)} saved)"
    if et == ActivityEventType.SELF_HEAL:
        return f"({event.agent_id[:8]}) {d.get('action', 'heal')} ({d.get('diagnosis', '')})"
    return ""


async def _run(
    runtime: Runtime,
    description: str,
    *,
    root_agent: Agent | None = None,
    resume_id: str | None = None,
) -> tuple[Agent, StateWriter]:
    """Run a task to completion, streaming state/events to files and showing
    a single-line token counter while it works."""
    writer = _make_writer(runtime)
    runtime.event_bus.clear()
    attach_events(runtime, writer)

    progress = _ProgressLine(
        lambda: runtime.total_usage().get("total_tokens", 0)
    )
    ask_queue: asyncio.Queue[str] = asyncio.Queue()
    _install_ask_tool(runtime, ask_queue)

    def label_event(event) -> None:
        label = _progress_label(event)
        if label:
            progress.set_label(label)

    runtime.on_activity(label_event)

    async def run_task() -> Agent:
        if resume_id:
            return await runtime.resume(resume_id)
        return await runtime.run(
            description, role=ORCHESTRATOR_ROLE, root_agent=root_agent
        )

    task = asyncio.ensure_future(run_task())
    progress.start()
    try:
        while not task.done():
            if not ask_queue.empty():
                question = ask_queue.get_nowait()
                progress.stop()
                console.print()
                answer = Prompt.ask(f"[bold cyan]Agent asks:[/] {question}")
                ask_queue.put_nowait(answer.strip())
                progress.start()
            await asyncio.sleep(0.1)
        root = await task
    finally:
        progress.stop()
        writer.snapshot(runtime)
    return root, writer


def _print_outcome(root: Agent) -> None:
    if root.last_report:
        console.print(f"\n[bold green]\u2713 Agent {root.id[:8]}[/]")
        console.print(f"  {root.last_report.summary}\n")
    elif root.last_failure:
        console.print(f"\n[bold red]\u2717 Agent {root.id[:8]}[/] failed: {root.last_failure.error[:200]}\n")


def _print_provenance(runtime: Runtime, agent_id: str) -> None:
    """Render the task/trace/artifact/commit mapping for a single agent id."""
    agent_id = agent_id.strip()
    if not agent_id:
        console.print("[yellow]Usage: /provenance <agent_id> (also /trace <id>, /artifacts <id>)[/]")
        return
    prov = runtime.provenance(agent_id)
    if not prov["artifact_ids"] and not prov["trace_path"] and not prov["commit_ids"]:
        console.print(f"[red]No records found for agent id '{agent_id}'.[/]  Try /artifacts to list all.")
        return
    table = Table(title=f"Provenance — agent {agent_id}", title_justify="left")
    table.add_column("Key")
    table.add_column("Value")
    table.add_row("task_id", prov["task_id"] or "(unknown)")
    table.add_row("status", prov["status"] or "(unknown)")
    table.add_row("trace", prov["trace_path"] or "(no trace on disk)")
    table.add_row("commits", ", ".join(prov["commit_ids"]) or "(none)")
    for aid, p in zip(prov["artifact_ids"], prov["artifact_paths"]):
        table.add_row(f"artifact {aid}", p)
    console.print(table)


def _print_artifacts(runtime: Runtime, fragment: str = "") -> None:
    """List all artifacts, optionally filtered by an agent_id substring."""
    rows = runtime.artifact_index_records()
    if fragment:
        rows = [r for r in rows if fragment in r["agent_id"] or fragment in r["artifact_id"]]
    if not rows:
        console.print("[dim]No artifacts.[/]")
        return
    table = Table(title="Artifacts", title_justify="left")
    table.add_column("artifact")
    table.add_column("agent")
    table.add_column("headline")
    for r in rows:
        table.add_row(r["artifact_id"], r["agent_id"], (r["headline"] or "")[:48])
    console.print(table)


def _write_provenance_index(runtime: Runtime) -> Path:
    path = runtime.write_provenance_index()
    console.print(f"[bold cyan]index.jsonl → {path}[/]")
    return path


def _run_batch(runtime: Runtime, prompt: str, *, resume_id: str | None = None) -> None:
    root, writer = asyncio.run(_run(runtime, prompt, resume_id=resume_id))
    _print_outcome(root)

    usage = runtime.total_usage()
    console.print(f"[dim]Agents: {runtime.agent_count()} | Commits: {runtime.repository.count()} | Tokens: {usage['total_tokens']}[/]")
    _print_tree(runtime)
    _print_state_files(writer)

    # Per-run provenance index: a flat, greppable artifact->agent map.
    if runtime.artifact_store.all():
        _write_provenance_index(runtime)


def _print_state_files(writer: StateWriter) -> None:
    console.print(
        f"[dim]State: {writer.agents_txt_path}, {writer.tree_path}, {writer.stats_path}, {writer.events_path}[/]"
    )


def _print_tree(runtime: Runtime) -> None:
    """Print a plain-text agent tree (ids, status, messages, token usage)."""
    console.print(render_text_tree(build_agent_tree(runtime)))


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
            parts = text.strip().split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""
            if cmd == "/help":
                console.print("[bold]Commands:[/]  /help  /tree  /agents  /provenance <id>  /trace <id>  /artifacts [id]  /index  /checkpoints  /resume <id>  /reset  exit/quit")
                console.print("  /tree             — print the agent tree (id/status/messages/tokens)")
                console.print("  /provenance <id>  — task/trace/artifact/commit map for an agent")
                console.print("  /trace <id>       — path to an agent's trace.jsonl on disk")
                console.print("  /artifacts [id]   — list artifacts (optionally filter by agent)")
                console.print("  /index            — write the run's index.jsonl")
                console.print("  /checkpoints      — list persisted (resumable) agent checkpoints")
                console.print("  /resume <id>      — resume an agent from its persisted checkpoint")
            elif cmd == "/checkpoints":
                if not runtime.checkpoint_store:
                    console.print("[yellow]No checkpoint store configured on this runtime.[/]")
                else:
                    ids = runtime.checkpoint_store.list_ids()
                    console.print((", ".join(ids)) if ids else "[dim]No checkpoints on disk.[/dim]")
            elif cmd == "/resume":
                if not runtime.checkpoint_store:
                    console.print("[yellow]No checkpoint store configured on this runtime.[/]")
                elif not arg.strip():
                    console.print("[yellow]Usage: /resume <agent_id>  (see /checkpoints)[/]")
                else:
                    root, writer = await _run(runtime, "", resume_id=arg.strip())
                    _print_outcome(root)
                    _print_state_files(writer)
            elif cmd == "/tree":
                _print_tree(runtime)
            elif cmd == "/agents":
                u = runtime.total_usage()
                console.print(f"Agents: {runtime.agent_count()}  Commits: {runtime.repository.count()}  Tokens: {u['total_tokens']}")
            elif cmd == "/provenance":
                _print_provenance(runtime, arg)
            elif cmd == "/trace":
                prov = runtime.provenance(arg.strip())
                console.print(prov["trace_path"] or f"[red]No trace on disk for agent '{arg.strip()}'. Try /artifacts[/]")
            elif cmd == "/artifacts":
                _print_artifacts(runtime, arg)
            elif cmd == "/index":
                _write_provenance_index(runtime)
            elif cmd == "/reset":
                runtime.reset()
                root_agent = None
                console.print("Runtime reset.")
            else:
                console.print(f"Unknown: {cmd}. Try /help")
            continue

        root, writer = await _run(runtime, text, root_agent=root_agent)
        if root_agent is None:
            root_agent = root
        _print_outcome(root)
        _print_state_files(writer)


def main() -> None:
    args = _parse_args()

    runtime = build_runtime(args)

    if args.resume:
        _run_batch(runtime, "", resume_id=args.resume)
    elif args.m:
        _run_batch(runtime, Path(args.m).read_text())
    elif args.prompt:
        _run_batch(runtime, " ".join(args.prompt))
    else:
        asyncio.run(_run_interactive_async(runtime))


if __name__ == "__main__":
    main()