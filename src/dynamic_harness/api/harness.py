from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable

from ..core.agent import Agent
from ..core.events_format import format_event
from ..core.runner import AgentRunner
from ..core.runtime import Runtime
from ..core.task import ActivityEvent, ActivityEventType, Failure, ReportPayload, Task

logger = logging.getLogger("dynamic_harness")


class Harness:
    """Programmatic Python API for the Dynamic Harness agent runtime.

    Provides moderate continuous feedback via a configurable logger. Users
    can override callbacks for report, failure, and activity events.

    Usage::

        from dynamic_harness import Harness

        # With paths (creates Runtime internally):
        harness = Harness(artifact_root="./artifacts", repo_root="./repo")
        harness.run("List all Python files in the project")

        # With existing Runtime (full control):
        from dynamic_harness import Runtime
        rt = Runtime(artifact_root=..., repo_root=...)
        harness = Harness(runtime=rt)
        harness.run("Do something")

        for tag, summary in harness.last_reports:
            print(f"[{tag}] {summary}")
    """

    def __init__(
        self,
        artifact_root: str | Path | None = None,
        repo_root: str | Path | None = None,
        trace_root: str | Path | None = None,
        llm_config: dict[str, Any] | None = None,
        runtime: Runtime | None = None,
        *,
        llm: Any | None = None,
        verbose: bool = True,
    ) -> None:
        if runtime is not None:
            self._runtime = runtime
        else:
            if artifact_root is None or repo_root is None:
                raise ValueError(
                    "Either provide `runtime` or both `artifact_root` and `repo_root`"
                )
            self._runtime = Runtime(
                artifact_root=Path(artifact_root),
                repo_root=Path(repo_root),
                trace_root=Path(trace_root) if trace_root else None,
            )

        self._runner = AgentRunner(self._runtime)
        self._verbose = verbose

        if llm is not None:
            self._runtime.set_llm(llm)
        elif llm_config:
            self._configure_llm(llm_config)

        self._runtime.on_report(self._on_report)
        self._runtime.on_failure(self._on_failure)
        self._runtime.on_activity(self._on_activity)

        self._user_on_report: Callable[[str, ReportPayload], None] | None = None
        self._user_on_failure: Callable[[str, Failure], None] | None = None
        self._user_on_activity: Callable[[ActivityEvent], None] | None = None

    def _configure_llm(self, config: dict[str, Any]) -> None:
        from ..llm.openai_provider import OpenAIProvider

        llm = OpenAIProvider(
            model=config.get("model", "deepseek/deepseek-v4-flash"),
            base_url=config.get("base_url", "https://openrouter.ai/api/v1"),
            api_key=config.get("api_key", ""),
            verify_ssl=config.get("verify_ssl", True),
        )
        self._runtime.set_llm(llm)

    def _on_report(self, agent_id: str, payload: ReportPayload) -> None:
        if self._verbose:
            logger.info(
                "\u2713 %s report done \u2014 %s",
                agent_id[:8], payload.summary[:80],
            )
        if self._user_on_report:
            self._user_on_report(agent_id, payload)

    def _on_failure(self, agent_id: str, fail: Failure) -> None:
        if self._verbose:
            logger.warning("\u2717 %s fail: %s", agent_id[:8], fail.error[:80])
        if self._user_on_failure:
            self._user_on_failure(agent_id, fail)

    def _on_activity(self, event: ActivityEvent) -> None:
        if self._user_on_activity:
            self._user_on_activity(event)
        if not self._verbose:
            return
        line = format_event(event, emoji=False, show_args=True)
        if line is None:
            return
        if event.event_type == ActivityEventType.SAFETY_WARNING:
            logger.warning("%s %s", event.agent_id[:8], line.strip())
        elif event.event_type in (ActivityEventType.DELEGATION_START,
                                  ActivityEventType.DELEGATION_END):
            logger.info("  %s", line.strip())
        else:
            logger.debug("  %s", line.strip())

    @property
    def runtime(self) -> Runtime:
        return self._runtime

    @property
    def last_reports(self) -> list[tuple[str, str]]:
        return self._runner.last_reports

    @property
    def agent_count(self) -> int:
        return self._runtime.agent_count()

    @property
    def commit_count(self) -> int:
        return self._runtime.repository.count()

    @property
    def total_usage(self) -> dict[str, Any]:
        return self._runtime.total_usage()

    def on_report(self, handler: Callable[[str, ReportPayload], None]) -> None:
        self._user_on_report = handler

    def on_failure(self, handler: Callable[[str, Failure], None]) -> None:
        self._user_on_failure = handler

    def on_activity(self, handler: Callable[[ActivityEvent], None]) -> None:
        self._user_on_activity = handler

    def run(self, description: str) -> None:
        """Run a single task synchronously (creates a new event loop)."""
        asyncio.run(self._runner.run(description))
        if self._verbose:
            usage = self.total_usage
            logger.info(
                "Done \u2014 %s agents, %s commits, %s tokens",
                self.agent_count, self.commit_count, usage.get("total_tokens", 0),
            )

    async def run_async(self, description: str) -> None:
        """Run a single task asynchronously (for use inside an existing event loop)."""
        await self._runner.run(description)
        if self._verbose:
            usage = self.total_usage
            logger.info(
                "Done \u2014 %s agents, %s commits, %s tokens",
                self.agent_count, self.commit_count, usage.get("total_tokens", 0),
            )

    def run_file(self, path: str | Path) -> None:
        """Read a prompt from a file and run it synchronously."""
        prompt = Path(path).read_text()
        self.run(prompt)

    async def run_file_async(self, path: str | Path) -> None:
        """Read a prompt from a file and run it asynchronously."""
        prompt = Path(path).read_text()
        await self.run_async(prompt)

    def reset(self) -> None:
        self._runtime.reset()
        self._runner = AgentRunner(self._runtime)