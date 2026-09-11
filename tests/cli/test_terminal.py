from __future__ import annotations

import asyncio

from dynamic_harness.cli.terminal import _run_command, _submit_input
from dynamic_harness.core.task import Task


def test_run_command_returns_false_for_plain_text(runtime):
    assert asyncio.run(_run_command(runtime, "hello")) is False


def test_run_command_tree_is_allowed_during_run(runtime):
    runtime.delegate(Task(description="root"))
    assert asyncio.run(_run_command(runtime, "/tree", allow_run_commands=False)) is True


def test_run_command_agents_is_allowed_during_run(runtime):
    runtime.delegate(Task(description="root"))
    assert asyncio.run(_run_command(runtime, "/agents", allow_run_commands=False)) is True


def test_run_command_reset_blocked_during_run(runtime):
    aid = runtime.delegate(Task(description="root")).id
    asyncio.run(_run_command(runtime, "/reset", allow_run_commands=False))
    assert runtime.get_agent(aid) is not None  # not reset


def test_run_command_reset_allowed_when_idle(runtime):
    runtime.delegate(Task(description="root"))
    asyncio.run(_run_command(runtime, "/reset"))
    assert runtime.agent_count() == 0


def test_submit_input_routes_message_to_active_root(runtime):
    agent = runtime.delegate(Task(description="root"))
    runtime._active_root = agent
    asyncio.run(_submit_input(runtime, "carry on"))
    assert agent._inject_queue.qsize() == 1


def test_submit_input_routes_command_ignores_no_root(runtime):
    assert asyncio.run(_submit_input(runtime, "/agents")) is None


def test_ask_handoff_returns_answer_not_question(runtime):
    """The ask tool must yield the user's answer, never its own question.

    Regression: the question and answer used to ride one shared queue, so the
    tool's ``get()`` could hand the question back to the agent as its "answer"
    whenever it resumed before the terminal consumed the question.
    """
    from dynamic_harness.cli.terminal import _install_ask_tool

    async def scenario() -> tuple[str, str]:
        qq: asyncio.Queue[str] = asyncio.Queue()
        aq: asyncio.Queue[str] = asyncio.Queue()
        _install_ask_tool(runtime, qq, aq)
        _, fn = runtime.tool_registry.get("ask")

        ask_task = asyncio.ensure_future(fn(ctx=None, question="what color?"))
        asked = await asyncio.wait_for(qq.get(), timeout=1)
        aq.put_nowait("blue")
        return asked, await asyncio.wait_for(ask_task, timeout=1)

    asked, result = asyncio.run(scenario())
    assert asked == "what color?"
    assert result == "blue"


def test_drive_non_tty_answers_ask(runtime, monkeypatch):
    """The non-TTY drive loop forwards an ask question to the operator's input
    and returns the answer to the waiting agent."""
    from dynamic_harness.cli import terminal
    from dynamic_harness.cli.terminal import _drive

    class _FakeStream:
        def isatty(self) -> bool:
            return False

    monkeypatch.setattr(terminal.sys, "stdin", _FakeStream())
    monkeypatch.setattr(terminal.sys, "stdout", _FakeStream())
    answers = iter(["size L"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))

    async def run() -> tuple[object, list[str]]:
        qq: asyncio.Queue[str] = asyncio.Queue()
        aq: asyncio.Queue[str] = asyncio.Queue()
        qq.put_nowait("what size?")

        async def finish() -> object:
            await asyncio.sleep(0.05)
            return ("done", object())

        task = asyncio.ensure_future(finish())
        result = await _drive(runtime, task, qq, aq, {"label": ""})
        got: list[str] = []
        while not aq.empty():
            got.append(aq.get_nowait())
        return result, got

    result, got = asyncio.run(run())
    assert got == ["size L"]
    agent_sentinel = result[1]
    assert result[0] == "done"
    assert isinstance(agent_sentinel, object)


def test_drive_tty_ask_roundtrip(runtime, monkeypatch):
    """Full interactive ask round-trip through the raw-mode ``_drive`` loop.

    Drives the real TTY editor over a pty pair: the 'user' sees the ``[ask]``
    prompt appear, types an answer, and the waiting ask-tool coroutine receives
    exactly that answer (never the question)."""
    import os
    import pty
    import select
    import threading

    from dynamic_harness.cli import terminal
    from dynamic_harness.cli.terminal import _drive

    master, slave = pty.openpty()

    class _TtyStream:
        def __init__(self, fd):
            self.fd = fd
            self.encoding = "utf-8"

        def isatty(self) -> bool:
            return True

        def fileno(self) -> int:
            return self.fd

        def write(self, s: str | bytes) -> None:
            if isinstance(s, str):
                s = s.encode()
            os.write(self.fd, s)

        def flush(self) -> None:
            pass

    stream = _TtyStream(slave)
    monkeypatch.setattr(terminal.sys, "stdin", stream)
    monkeypatch.setattr(terminal.sys, "stdout", stream)

    qq: asyncio.Queue[str] = asyncio.Queue()
    aq: asyncio.Queue[str] = asyncio.Queue()
    received: list[str] = []

    def master_driver() -> None:
        deadline = __import__("time").time() + 10
        out = b""
        while __import__("time").time() < deadline:
            r, _, _ = select.select([master], [], [], 0.2)
            if not r:
                continue
            chunk = os.read(master, 4096)
            if not chunk:
                break
            out += chunk
            if not received and b"what do you like?" in out:
                out = b""
                os.write(master, b"blue\r")
            if received:
                return

    t = threading.Thread(target=master_driver, daemon=True)
    t.start()

    async def run_task():
        from dynamic_harness.cli.terminal import _install_ask_tool
        _install_ask_tool(runtime, qq, aq)
        _, fn = runtime.tool_registry.get("ask")
        ans = await fn(ctx=None, question="what do you like?")
        received.append(ans)
        return f"done-{ans}"

    async def run() -> str:
        return await _drive(runtime, asyncio.ensure_future(run_task()), qq, aq, {"label": ""})

    result = asyncio.run(run())
    t.join(timeout=5)

    assert received == ["blue"]
    assert result == "done-blue"


def test_drive_tty_prints_root_assistant_reply(runtime, monkeypatch):
    """The top agent's text replies stream into the terminal above the live
    prompt (children's chatter must stay invisible)."""
    import os
    import pty
    import select
    import threading
    import time

    from rich.console import Console

    from dynamic_harness.cli import terminal
    from dynamic_harness.cli.terminal import _drive
    from dynamic_harness.core.task import ActivityEvent, ActivityEventType

    master, slave = pty.openpty()

    class _TtyStream:
        def __init__(self, fd):
            self.fd = fd
            self.encoding = "utf-8"

        def isatty(self) -> bool:
            return True

        def fileno(self) -> int:
            return self.fd

        def write(self, s: str | bytes) -> None:
            if isinstance(s, str):
                s = s.encode()
            os.write(self.fd, s)

        def flush(self) -> None:
            pass

    stream = _TtyStream(slave)
    monkeypatch.setattr(terminal.sys, "stdin", stream)
    monkeypatch.setattr(terminal.sys, "stdout", stream)
    monkeypatch.setattr(terminal, "console", Console(file=stream, force_terminal=True))

    root = runtime.delegate(Task(description="root"))
    runtime._active_root = root

    async def run_task():
        runtime.emit_activity(ActivityEvent(
            agent_id=root.id,
            event_type=ActivityEventType.ASSISTANT_REPLY,
            data={"content": "hello from the root agent"},
        ))
        await asyncio.sleep(0.2)

    async def run():
        qq: asyncio.Queue[str] = asyncio.Queue()
        aq: asyncio.Queue[str] = asyncio.Queue()
        return await _drive(runtime, asyncio.ensure_future(run_task()), qq, aq, {"label": ""})

    captured: list[bytes] = []

    def master_driver() -> None:
        deadline = time.time() + 8
        out = b""
        while time.time() < deadline:
            r, _, _ = select.select([master], [], [], 0.2)
            if not r:
                continue
            try:
                chunk = os.read(master, 4096)
            except OSError:
                break
            if not chunk:
                break
            out += chunk
            if b"hello from the root agent" in out:
                captured.append(out)
                return

    t = threading.Thread(target=master_driver, daemon=True)
    t.start()
    asyncio.run(run())
    t.join(timeout=8)

    assert captured, "root assistant reply was never printed to the terminal"


def test_drive_tty_ignores_child_assistant_reply(runtime, monkeypatch):
    """Only the root's replies are streamed; delegated children's text stays
    out of the operator's terminal."""
    import os
    import pty
    import select
    import threading
    import time

    from rich.console import Console

    from dynamic_harness.cli import terminal
    from dynamic_harness.cli.terminal import _drive
    from dynamic_harness.core.task import ActivityEvent, ActivityEventType

    master, slave = pty.openpty()

    class _TtyStream:
        def __init__(self, fd):
            self.fd = fd
            self.encoding = "utf-8"

        def isatty(self) -> bool:
            return True

        def fileno(self) -> int:
            return self.fd

        def write(self, s: str | bytes) -> None:
            if isinstance(s, str):
                s = s.encode()
            os.write(self.fd, s)

        def flush(self) -> None:
            pass

    stream = _TtyStream(slave)
    monkeypatch.setattr(terminal.sys, "stdin", stream)
    monkeypatch.setattr(terminal.sys, "stdout", stream)
    console = Console(file=stream, force_terminal=True)
    monkeypatch.setattr(terminal, "console", console)

    root = runtime.delegate(Task(description="root"))
    child = runtime.delegate(Task(description="child"), parent=root)
    runtime._active_root = root

    async def run_task():
        # A child's reply must be suppressed ...
        runtime.emit_activity(ActivityEvent(
            agent_id=child.id,
            event_type=ActivityEventType.ASSISTANT_REPLY,
            data={"content": "child chatter, keep quiet"},
        ))
        # ... while the root's own reply still streams (render signal).
        runtime.emit_activity(ActivityEvent(
            agent_id=root.id,
            event_type=ActivityEventType.ASSISTANT_REPLY,
            data={"content": "root speaking now"},
        ))
        await asyncio.sleep(0.2)

    async def run():
        qq: asyncio.Queue[str] = asyncio.Queue()
        aq: asyncio.Queue[str] = asyncio.Queue()
        return await _drive(runtime, asyncio.ensure_future(run_task()), qq, aq, {"label": ""})

    captured: list[bytes] = []

    def master_driver() -> None:
        deadline = time.time() + 8
        out = b""
        while time.time() < deadline:
            r, _, _ = select.select([master], [], [], 0.2)
            if not r:
                continue
            try:
                chunk = os.read(master, 4096)
            except OSError:
                break
            if not chunk:
                break
            out += chunk
            if b"root speaking now" in out:
                captured.append(out)
                return

    t = threading.Thread(target=master_driver, daemon=True)
    t.start()
    asyncio.run(run())
    t.join(timeout=8)

    assert captured, "root assistant reply was never printed to the terminal"
    assert b"child chatter" not in captured[0]


def test_prune_done_tasks_survives_inner_discard():
    """Regression: _sweep_prints used set.difference_update(gen) over the same
    set — CPython rejects mutating a set while iterating it. With a single
    completed task the discard shrank the set mid-iteration and raised
    'Set changed size during iteration'."""
    from dynamic_harness.cli.terminal import _prune_done_tasks

    async def _done() -> None:
        return None

    loop = asyncio.new_event_loop()
    try:
        done = loop.create_task(_done())
        loop.run_until_complete(done)
        pending = {done}
        _prune_done_tasks(pending)
        assert pending == set()
        # An unfinished task must stay put.
        waiting: set[asyncio.Task[None]] = set()
        _prune_done_tasks(waiting)
        assert waiting == set()
    finally:
        loop.close()


def test_print_reply_treats_agent_text_as_data_not_markup(monkeypatch):
    """Brackets/numbers in a reply must survive verbatim: Rich must not parse
    the agent's words as markup (MarkupError) or highlight them."""
    import io

    from rich.console import Console

    from dynamic_harness.cli import terminal
    from dynamic_harness.cli.terminal import _print_reply

    out = io.StringIO()
    monkeypatch.setattr(
        terminal, "console",
        Console(file=out, force_terminal=False, color_system=None, width=200),
    )
    _print_reply("ab" * 6, "[1] 'the [x] fix' vs step 2\n  second line")
    text = out.getvalue()
    assert "[1] 'the [x] fix' vs step 2" in text
    assert "second line" in text
    assert text.replace(" ", "").startswith("abababab[1]")  # id prefix present
