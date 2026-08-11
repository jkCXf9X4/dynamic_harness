from __future__ import annotations

import pytest

from dynamic_harness.cli.tui import TUI
from dynamic_harness.core.task import Task


@pytest.mark.asyncio
async def test_tui_composes_and_applies_tree(runtime) -> None:
    app = TUI(runtime=runtime)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert app.query_one("#sidebar")
        assert app.query_one("#output")
        assert app.query_one("#input")

        root = runtime.delegate(Task(description="a root task"))
        app._apply_tree()
        await pilot.pause()

        assert app._root_agent is None
        root.task.status  # ensure no crash while navigating node data


@pytest.mark.asyncio
async def test_tui_apply_tree_handles_empty(runtime) -> None:
    app = TUI(runtime=runtime)
    async with app.run_test(size=(100, 30)) as pilot:
        app._apply_tree()
        await pilot.pause()


@pytest.mark.asyncio
async def test_tui_apply_tree_nested(runtime) -> None:
    app = TUI(runtime=runtime)
    async with app.run_test(size=(100, 30)) as pilot:
        root = runtime.delegate(Task(description="root"))
        child = runtime.delegate(Task(description="child"), parent=root)
        grand = runtime.delegate(Task(description="grandchild"), parent=child)
        app._apply_tree()
        await pilot.pause()
        assert root.id and child.id and grand.id