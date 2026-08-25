from __future__ import annotations

import argparse
import asyncio
import os
import select
import sys
import termios
import tty
from pathlib import Path

from rich.console import Console
from rich.table import Table

from ..core.agent import Agent
from ..core.prompts import ORCHESTRATOR_ROLE
from ..core.task import ActivityEventType
from ..core.tools.agents import TOOL_ASK_DEF
from ..core.runtime import Runtime
from .common import build_runtime
from .present import build_agent_tree, render_text_tree
from .profile import RunProfiler, run_meta
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
    parser.add_argument("--profile", action="store_true",
                        help="Profile the live session; write profile.{prof,txt,json} + meta.json under the run root (or --profile-dir)")
    parser.add_argument("--profile-dir", metavar="DIR",
                        help="Directory for profiling artifacts (default: <run root>/profile)")
    return parser.parse_args(argv)


def _install_ask_tool(
    runtime: Runtime,
    question_queue: asyncio.Queue[str],
    answer_queue: asyncio.Queue[str],
) -> None:
    async def _ask(*, ctx, question: str) -> str:
        await question_queue.put(question)
        return (await answer_queue.get()).strip()
    runtime.tool_registry.register(TOOL_ASK_DEF, _ask)


def _make_writer(runtime: Runtime) -> StateWriter:
    """Persist overview files in the run root, next to artifacts/repo/traces."""
    return StateWriter(runtime.artifact_store.root.parent)


def _render_line(prefix: str, buf: list[str], pos: int) -> None:
    """Redraw the single live line: `\\r` + clear + prefix + buffer, cursor at pos."""
    sys.stdout.write("\r\x1b[2K")
    sys.stdout.write(prefix + "".join(buf))
    back = len(buf) - pos
    if back > 0:
        sys.stdout.write(f"\x1b[{back}D")
    sys.stdout.flush()


def _progress_status(runtime: Runtime, label: str) -> str:
    tokens = runtime.total_usage().get("total_tokens", 0)
    return f"{tokens} tokens" + (f" \u00b7 {label}" if label else "")


async def _submit_input(runtime: Runtime, line: str) -> None:
    """Route a mid-run line: `/command` becomes a command; anything else is
    injected into the active root agent (queued while it works, applied
    immediately while it is blocked on its children)."""
    line = line.strip()
    if not line:
        return
    if line.startswith("/"):
        await _run_command(runtime, line, allow_run_commands=False)
        return
    root = runtime.active_root()
    if root is not None and root.task.status.value not in (
        "completed", "failed", "escalated",
    ):
        root.submit_input(line)
    else:
        console.print("[yellow]No active agent to receive input.[/yellow]")


async def _drive(
    runtime: Runtime,
    task: asyncio.Task[Agent],
    question_queue: asyncio.Queue[str],
    answer_queue: asyncio.Queue[str],
    label_state: dict[str, str],
) -> Agent | None:
    """Run ``task`` to completion with an always-available input line.

    A lightweight single-line editor shows a live token counter + activity label
    and a ``>>>`` prompt. Enter submits the line (commands or agent input); the
    agent-``ask`` tool swaps the prompt to ``[ask] <question>`` and returns your
    answer. Ctrl+C cancels the run. Non-TTY sessions skip the editor entirely
    and just await the task (clean for batch/pipelines).
    """
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        while not task.done():
            while not question_queue.empty():
                q = question_queue.get_nowait().strip()
                try:
                    answer = await asyncio.to_thread(input, f"{q}\n> ")
                except EOFError:
                    answer = ""
                answer_queue.put_nowait(answer.strip())
            await asyncio.sleep(0.2)
        return await task

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    buf: list[str] = []
    pos = 0
    mode = "user"
    qtext = ""

    def prefix() -> str:
        if mode == "ask":
            return f"[ask] {qtext} \xbb "
        return "\xbb "

    def draw() -> None:
        _render_line(_progress_status(runtime, label_state.get("label", "")) + " " + prefix(), buf, pos)

    try:
        tty.setraw(fd)
        draw()
        while not task.done():
            if mode == "user" and not question_queue.empty():
                mode = "ask"
                qtext = question_queue.get_nowait().strip()
                buf = []
                pos = 0
            ready, _, _ = select.select([sys.stdin], [], [], 0.1)
            if ready:
                b = os.read(fd, 1)
                if not b:
                    continue
                by = b[0]
                if by in (0x0D, 0x0A):  # Enter
                    sys.stdout.write("\r\n")
                    sys.stdout.flush()
                    line = "".join(buf)
                    if mode == "ask":
                        answer_queue.put_nowait(line.strip())
                        mode = "user"
                        qtext = ""
                    else:
                        await _submit_input(runtime, line)
                    buf = []
                    pos = 0
                elif by == 0x03:  # Ctrl+C
                    sys.stdout.write("\r\n")
                    sys.stdout.flush()
                    task.cancel()
                    break
                elif by == 0x04:  # Ctrl+D
                    buf = []
                    pos = 0
                elif by in (0x7F, 0x08):  # backspace
                    if pos > 0:
                        del buf[pos - 1]
                        pos -= 1
                elif by >= 0x80:  # UTF-8 multibyte
                    extra = b""
                    if 0xC0 <= by <= 0xDF:
                        extra = os.read(fd, 1)
                    elif 0xE0 <= by <= 0xEF:
                        extra = os.read(fd, 2)
                    elif 0xF0 <= by <= 0xF7:
                        extra = os.read(fd, 3)
                    ch = (b + extra).decode("utf-8", "replace")
                    buf.insert(pos, ch)
                    pos += 1
                elif by >= 0x20:
                    buf.insert(pos, chr(by))
                    pos += 1
            await asyncio.sleep(0)
            draw()
        if task.cancelled():
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
            return None
        root = await task
        sys.stdout.write("\r\n")
        sys.stdout.flush()
        return root
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


async def _run(
    runtime: Runtime,
    description: str,
    *,
    root_agent: Agent | None = None,
    resume_id: str | None = None,
) -> tuple[Agent | None, StateWriter]:
    """Run a task to completion, streaming state/events to files and keeping a
    live single-line token counter + always-available input while it works."""
    writer = _make_writer(runtime)
    runtime.event_bus.clear()
    attach_events(runtime, writer)

    question_queue: asyncio.Queue[str] = asyncio.Queue()
    answer_queue: asyncio.Queue[str] = asyncio.Queue()
    _install_ask_tool(runtime, question_queue, answer_queue)

    label_state: dict[str, str] = {"label": ""}

    def label_event(event) -> None:
        label = _progress_label(event)
        if label:
            label_state["label"] = label

    runtime.on_activity(label_event)

    async def run_task() -> Agent:
        if resume_id:
            return await runtime.resume(resume_id)
        return await runtime.run(
            description, role=ORCHESTRATOR_ROLE, root_agent=root_agent
        )

    task = asyncio.ensure_future(run_task())
    root = await _drive(runtime, task, question_queue, answer_queue, label_state)
    writer.snapshot(runtime)
    return root, writer


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


def _print_outcome(root: Agent | None) -> None:
    if root is None:
        return
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
    console.print(render_text_tree(build_agent_tree(runtime)), markup=False)


async def _run_command(
    runtime: Runtime, text: str, *, allow_run_commands: bool = True
) -> bool:
    """Dispatch a `/...` command. Returns True if ``text`` was a command.

    ``allow_run_commands`` gates mutating commands (`/resume`, `/reset`) that
    must not run while another run is active; inspection commands (`/tree`,
    `/agents`, ...) are always allowed so the operator can watch progress live.
    """
    text = text.strip()
    if not text.startswith("/"):
        return False
    parts = text.split(maxsplit=1)
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
        if not allow_run_commands:
            console.print("[yellow]/resume is not allowed while a run is active.[/]")
        elif not runtime.checkpoint_store:
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
        if not allow_run_commands:
            console.print("[yellow]/reset is not allowed while a run is active.[/]")
        else:
            runtime.reset()
            console.print("Runtime reset.")
    else:
        console.print(f"Unknown: {cmd}. Try /help")
    return True


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
            await _run_command(runtime, text)
            continue

        root, writer = await _run(runtime, text, root_agent=root_agent)
        if root_agent is None:
            root_agent = root
        _print_outcome(root)
        _print_state_files(writer)


def main() -> None:
    args = _parse_args()

    runtime = build_runtime(args)

    run_root = runtime.artifact_store.root.parent
    prof_base = Path(args.profile_dir).resolve() if args.profile_dir else run_root
    profiler = RunProfiler(prof_base, enabled=args.profile)
    profiler.start(meta=run_meta(args))

    try:
        if args.resume:
            _run_batch(runtime, "", resume_id=args.resume)
        elif args.m:
            _run_batch(runtime, Path(args.m).read_text())
        elif args.prompt:
            _run_batch(runtime, " ".join(args.prompt))
        else:
            asyncio.run(_run_interactive_async(runtime))
    finally:
        path = profiler.stop()
        if path is not None:
            prof_dir = prof_base / "profile"
            console.print(
                f"\n[bold cyan]Profile dumped → {path}[/] "
                f"({prof_dir / 'profile.txt'}, {prof_dir / 'profile.json'}, "
                f"{prof_dir / 'meta.json'})"
            )


if __name__ == "__main__":
    main()