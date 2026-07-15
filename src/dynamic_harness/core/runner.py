from __future__ import annotations

from .agent import Agent
from .runtime import Runtime
from .task import Task


class AgentRunner:
    """Pure agent lifecycle orchestrator with no rendering or I/O dependencies.

    Creates the root task via Runtime.delegate(), runs it with a direct
    await (the same pattern used by _tool_delegate for child agents), and
    collects the result from the root agent's _last_report / _last_failure.
    """

    def __init__(self, runtime: Runtime) -> None:
        self.runtime = runtime
        self.events: list[str] = []
        self.last_reports: list[tuple[str, str]] = []

    async def run(
        self,
        description: str,
        *,
        clear_events: bool = True,
        root_agent: Agent | None = None,
    ) -> None:
        if clear_events:
            self.events.clear()

        if root_agent is None:
            root = self.runtime.delegate(Task(description=description))
            await root.run()
        else:
            root = root_agent
            await root.continue_with_input(description)

        if root._last_report:
            tag = root.id[:8]
            self.events.append(f"{tag} report done")
            self.last_reports.append((tag, root._last_report.summary))
        if root._last_failure:
            tag = root.id[:8]
            self.events.append(f"{tag} fail: {root._last_failure.error}")
