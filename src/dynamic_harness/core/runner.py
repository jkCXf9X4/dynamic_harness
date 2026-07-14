from __future__ import annotations

import asyncio
from typing import Callable

from .agent import Agent
from .runtime import Runtime
from .task import Failure, ReportPayload, Task


class AgentRunner:
    """Pure agent lifecycle orchestrator with no rendering or I/O dependencies.

    Delegates, runs, and tracks agents. Emits lifecycle events via callbacks
    so that any UI layer (TUI, CLI, test harness) can observe progress
    without coupling to Rich, Textual, or any particular presentation
    library.
    """

    def __init__(self, runtime: Runtime) -> None:
        self.runtime = runtime
        self.events: list[str] = []
        self.last_reports: list[tuple[str, str]] = []

    def connect(self) -> None:
        self.runtime.on_report(self._on_report)
        self.runtime.on_failure(self._on_failure)

    def _on_report(self, agent_id: str, payload: ReportPayload) -> None:
        tag = agent_id[:8]
        self.events.append(f"{tag} report done")
        self.last_reports.append((tag, payload.summary))

    def _on_failure(self, agent_id: str, fail: Failure) -> None:
        tag = agent_id[:8]
        self.events.append(f"{tag} fail: {fail.error}")

    async def run(
        self,
        description: str,
        *,
        clear_events: bool = True,
        shutdown_event: asyncio.Event | None = None,
        on_update: Callable[[], None] | None = None,
        root_agent: Agent | None = None,
    ) -> None:
        if clear_events:
            self.events.clear()

        if root_agent is None:
            root = self.runtime.delegate(Task(description=description))
            root_task = asyncio.create_task(root.run())
        else:
            root_task = asyncio.create_task(root_agent.continue_with_input(description))

        while not root_task.done():
            if shutdown_event and shutdown_event.is_set():
                root_task.cancel()
                break
            if on_update:
                on_update()
            await asyncio.sleep(0.25)

        await root_task

    async def run_root(
        self,
        root: Agent,
        *,
        shutdown_event: asyncio.Event | None = None,
        on_update: Callable[[], None] | None = None,
    ) -> None:
        root_task = asyncio.create_task(root.run())

        while not root_task.done():
            if shutdown_event and shutdown_event.is_set():
                root_task.cancel()
                break
            if on_update:
                on_update()
            await asyncio.sleep(0.25)

        await root_task