from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from prompt_toolkit.application import run_in_terminal
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.shortcuts import PromptSession

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

_history: InMemoryHistory | None = None


def _make_session() -> PromptSession[str]:
    """A fresh prompt_toolkit session for the input line.

    Enter submits; bracket-pasted multi-line text is inserted literally and
    re-rendered once (fast, never corrupts the screen); Ctrl+J / Alt+Enter
    insert an explicit newline. prompt_toolkit owns all terminal specifics
    (bracketed paste, wide chars, word wrap, history).
    """
    global _history
    if _history is None:
        _history = InMemoryHistory()
    kb = KeyBindings()
    @kb.add("escape", "enter")
    @kb.add("c-j")
    def _insert_newline(event):
        event.app.current_buffer.insert_text("\n")
    return PromptSession(multiline=False, key_bindings=kb, history=_history)


async def _read_input(prompt: str) -> str:
    """Read a REPL input line (multi-line via paste / Ctrl+J) with editing."""
    if not sys.stdin.isatty():
        return input(prompt)
    session = _make_session()
    return await session.prompt_async(console.render_str(prompt).plain)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="dynamic-harness",
        description="Direct terminal mode for the recursive agent harness.",
    )
    parser.add_argument("prompt", nargs="*", help="Task description (inline)")
    parser.add_argument("-m", metavar="FILE", help="Read task prompt from file")
    parser.add_argument("--config", help="Path to harness.json config file")
    parser.add_argument("--temp", action="store_true", help="Use temporary directories")
    parser.add_argument("--model", help="LLM model name")
    parser.add_argument("--base-url", help="LLM API base URL")
    parser.add_argument("--api-key", help="LLM API key")
    parser.add_argument("--artifact-dir", help="Directory for artifacts")
    parser.add_argument("--repo-dir", help="Directory for commit repository")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive REPL mode")
    parser.add_argument("--resume", metavar="AGENT_ID", help="Resume an interrupted/failed agent from its persisted checkpoint")
    parser.add_argument("--profile", action="store_true",
                        help="Profile the live session; write profile.txt/json + meta.json under the run root (or --profile-dir)")
    parser.add_argument("--profile-dir", metavar="DIR",
                        help="Directory for profiling artifacts (default: <run root>/profile)")
    parser.add_argument("--profile-interval", metavar="MS", type=float, default=10.0,
                        help="Sampling interval in ms for --profile (default: 10)")
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


def _progress_status(runtime: Runtime, label: str) -> str:
    tokens = runtime.total_usage().get("total_tokens", 0)
    return f"{tokens} tokens" + (f" \u00b7 {label}" if label else "")


def _prune_done_tasks(tasks: set[asyncio.Task[None]]) -> None:
    """Drop completed tasks from ``tasks``.

    Snapshot-then-mutate: ``set.difference_update(gen_over_self)`` mutates the
    set while a generator is iterating it, which CPython rejects with "Set
    changed size during iteration" as soon as the first discard shrinks the
    set mid-iteration."""
    finished = {t for t in tasks if t.done()}
    if finished:
        tasks.difference_update(finished)


def _retire_task(t: asyncio.Task) -> None:
    """Cancel or consume ``t`` so teardown leaves no reported exception.

    prompt_toolkit surfaces Ctrl+C by raising ``KeyboardInterrupt`` inside the
    prompt coroutine, which asyncio stores on the task **and** re-raises out of
    the event loop (``Task.__step`` treats SystemExit/KeyboardInterrupt
    specially). The escaped exception never returns through ``_drive``'s loop,
    so the task's stored exception goes unretrieved — and when the last
    reference drops, asyncio logs "Task exception was never retrieved". Doing
    the retrieval here (before the task is dropped) silences that."""
    if t.done():
        if not t.cancelled():
            try:
                t.exception()
            except asyncio.CancelledError:
                pass
    else:
        t.cancel()


async def _close_prompt_task(t: asyncio.Task) -> None:
    """Cancel a live ``prompt_async`` task and wait for its teardown to finish.

    Merely ``cancel()``-ing a pending prompt_toolkit prompt schedules the
    cancellation but does not run the application's cleanup ``finally`` (which
    restores the terminal, removes the event-loop reader for the fd, and
    releases the renderer). If the next prompt (the ``>>>`` line back in the
    REPL) starts before that teardown runs, the two applications race over the
    same terminal input reader and the new prompt never receives keys — the
    application "no longer answers to input" after a run completes. Awaiting
    the cancelled task guarantees the cleanup completes first."""
    if t.done():
        try:
            t.exception()
        except (asyncio.CancelledError, Exception):
            pass
        return
    t.cancel()
    try:
        await t
    except (asyncio.CancelledError, Exception):
        pass


def _print_reply(agent_id: str, content: str) -> None:
    """Render one assistant reply above the live prompt.

    The agent's words are treated as data, never Rich markup: without this,
    brackets in a reply raise ``MarkupError`` and inline numbers get
    highlighted, garbling the streamed text."""
    from rich.text import Text

    lines = [ln for ln in content.splitlines() if ln.strip()]
    for i, ln in enumerate(lines):
        line = Text()
        if i == 0:
            line.append(agent_id[:8], style="bold cyan")
        else:
            line.append(" " * 9)
        line.append(f" {ln}")
        console.print(line)


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
        status = root.task.status.value if root is not None else "none"
        console.print(
            f"[yellow]No active agent to receive input (root is {status}).[/yellow]"
        )


async def _drive(
    runtime: Runtime,
    task: asyncio.Task[Agent],
    question_queue: asyncio.Queue[str],
    answer_queue: asyncio.Queue[str],
    label_state: dict[str, str],
    streamed_last: dict[str, str],
) -> Agent | None:
    """Run ``task`` to completion with an always-available input line.

    A prompt_toolkit input line shows a live token counter + activity label in
    the prompt; Enter submits (commands or agent input), pasting works fast and
    multi-line. The top agent's text replies stream into the terminal above the
    prompt as they happen (children's chatter stays invisible). The agent-``ask``
    tool swaps the live prompt to ``[ask] <question>`` and returns your answer.
    Ctrl+C cancels the run and exits the application. Non-TTY sessions skip the
    editor entirely and just await the task (clean for batch/pipelines).
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

    mode: dict[str, object] = {"ask": False, "qtext": ""}
    interrupted = False

    def message() -> str:
        if mode["ask"]:
            return f"[ask] {mode['qtext']} \u00bb "
        return f"{_progress_status(runtime, label_state.get('label', ''))} \u00bb "

    session = _make_session()

    # Stream the root agent's text replies into the terminal, printed above the
    # live prompt (suspend/render via prompt_toolkit so the input line survives).
    pending_prints: set[asyncio.Task[None]] = set()

    def display_root_reply(event) -> None:
        if event.event_type is not ActivityEventType.ASSISTANT_REPLY:
            return
        root = runtime.active_root()
        if root is None or event.agent_id != root.id:
            return
        content = (event.data.get("content") or "").strip()
        if not content:
            return
        streamed_last["content"] = content
        task = run_in_terminal(lambda: _print_reply(root.id, content))
        pending_prints.add(task)
        task.add_done_callback(lambda _t: _prune_done_tasks(pending_prints))

    runtime.on_activity(display_root_reply)

    async def prompt_once() -> str:
        return await session.prompt_async(message, refresh_interval=0.5)

    prompt_task: asyncio.Task[str] = asyncio.ensure_future(prompt_once())
    q_task: asyncio.Task[str] = asyncio.ensure_future(question_queue.get())
    try:
        while not task.done():
            done, _ = await asyncio.wait(
                {task, prompt_task, q_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if prompt_task in done:
                # Handle a completed prompt BEFORE a same-instant question so a
                # user's submitted line is never misrouted as an ask answer.
                try:
                    line = prompt_task.result()
                except asyncio.CancelledError:
                    line = None  # a queued ask interrupted the draft
                except KeyboardInterrupt:
                    sys.stdout.write("\r\n")
                    sys.stdout.flush()
                    task.cancel()
                    interrupted = True
                    break
                except EOFError:
                    line = None  # Ctrl+D at an empty prompt: no-op
                if mode["ask"]:
                    answer_queue.put_nowait(line.strip() if line else "")
                elif line:
                    await _submit_input(runtime, line)
                mode["ask"] = False
                mode["qtext"] = ""
                if task.done():
                    break
                prompt_task = asyncio.ensure_future(prompt_once())
            if q_task in done:
                # An agent question arrived: switch the live prompt to ``[ask]``.
                mode["qtext"] = q_task.result().strip()
                if not mode["ask"] and not prompt_task.done():
                    await _close_prompt_task(prompt_task)  # drop the partial draft
                    prompt_task = asyncio.ensure_future(prompt_once())
                mode["ask"] = True
                q_task = asyncio.ensure_future(question_queue.get())
    finally:
        if pending_prints:
            # Bounded drain: each print is microseconds, but never let teardown
            # hang on a wedged render task — cancel whatever is left over.
            _done, _stuck = await asyncio.wait(
                list(pending_prints), timeout=5.0,
                return_when=asyncio.ALL_COMPLETED,
            )
            pending_prints.clear()
            for t in _stuck:
                t.cancel()
        await _close_prompt_task(prompt_task)
        _retire_task(q_task)
    if interrupted:
        # Ctrl+C during a run: the run is already cancelled; clean it up and
        # raise so the whole application exits (see ``main``).
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
        raise KeyboardInterrupt
    if task.cancelled():
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
        return None
    root = await task
    return root


async def _run(
    runtime: Runtime,
    description: str,
    *,
    root_agent: Agent | None = None,
    resume_id: str | None = None,
) -> tuple[Agent | None, StateWriter, dict[str, str]]:
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
    streamed_last: dict[str, str] = {}
    try:
        root = await _drive(runtime, task, question_queue, answer_queue, label_state, streamed_last)
    finally:
        writer.snapshot(runtime, force=True)
    return root, writer, streamed_last


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


def _print_outcome(root: Agent | None, already_shown: str | None = None) -> None:
    if root is None:
        return
    if root.last_report:
        console.print(f"\n[bold green]\u2713 Agent {root.id[:8]}[/]")
        # A pure-chat turn (no tool calls) auto-reports its reply, which the
        # live stream already printed above the prompt — don't echo it twice.
        if (
            already_shown
            and root.last_report.summary
            and root.last_report.summary.strip() == already_shown.strip()
        ):
            return
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


def _run_batch(runtime: Runtime, prompt: str, *, resume_id: str | None = None) -> int:
    root, _writer, shown = asyncio.run(_run(runtime, prompt, resume_id=resume_id))
    _print_outcome(root, shown.get("content"))

    # Per-run provenance index: a flat, greppable artifact->agent map.
    if runtime.artifact_store.all():
        runtime.write_provenance_index()

    # Map the run outcome to a process exit code: 0 on success, non-zero on
    # failure/escalation so callers can detect a failed agent run.
    if root is None:
        return 1
    status = root.task.status.value
    if status in ("failed", "escalated"):
        return 1
    return 0


def _print_tree(runtime: Runtime) -> None:
    """Print a plain-text agent tree (ids, status, messages, token usage).

    Lines are printed one at a time with ``soft_wrap=True`` so rich doesn't
    reflow long lines across the terminal width — reflowing would break the
    box-drawing branch characters and indent the continuation oddly.
    """
    for line in render_text_tree(build_agent_tree(runtime)).splitlines():
        console.print(line, markup=False, soft_wrap=True)


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
            root, _writer, shown = await _run(runtime, "", resume_id=arg.strip())
            _print_outcome(root, shown.get("content"))
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
            text = await _read_input("[bold]>>>[/]")
        except (EOFError, KeyboardInterrupt):
            console.print()
            break

        text = text.strip()
        if not text:
            continue
        if text.lower() in ("exit", "quit"):
            break
        if text.startswith("/"):
            await _run_command(runtime, text)
            continue

        root, _writer, shown = await _run(runtime, text, root_agent=root_agent)
        if root_agent is None:
            root_agent = root
        _print_outcome(root, shown.get("content"))


def main() -> int:
    args = _parse_args()

    runtime = build_runtime(args)

    run_root = runtime.artifact_store.root.parent
    prof_base = Path(args.profile_dir).resolve() if args.profile_dir else run_root
    profiler = RunProfiler(prof_base, enabled=args.profile,
                           interval=args.profile_interval / 1000.0)
    profiler.start(meta=run_meta(args))

    exit_code = 0
    try:
        if args.resume:
            exit_code = _run_batch(runtime, "", resume_id=args.resume)
        elif args.m:
            exit_code = _run_batch(runtime, Path(args.m).read_text())
        elif args.prompt:
            exit_code = _run_batch(runtime, " ".join(args.prompt))
        else:
            asyncio.run(_run_interactive_async(runtime))
    except KeyboardInterrupt:
        # Ctrl+C exits the application (interactive run, idle prompt, or batch).
        sys.stdout.write("\r\n")
        console.print("[dim]Interrupted. Bye.[/]")
        exit_code = 130
    finally:
        path = profiler.stop()
        if path is not None:
            prof_dir = prof_base / "profile"
            console.print(
                f"\n[bold cyan]Profile dumped → {path}[/] "
                f"({prof_dir / 'profile.txt'}, {prof_dir / 'profile.json'}, "
                f"{prof_dir / 'meta.json'})"
            )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())