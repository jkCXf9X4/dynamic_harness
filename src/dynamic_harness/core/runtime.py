from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable
from uuid import uuid4

from ..artifact.store import Artifact, ArtifactStore, ArtifactView
from ..memory.repository import Commit, Repository
from .agent import Agent
from .capabilities import ToolRegistry, register_default_tools
from .task import BudgetRequest, Escalation, Failure, ReportPayload, Task, TaskStatus, ActivityEvent
from .trace import TraceStore

if TYPE_CHECKING:
    from ..config import HarnessConfig
    from ..llm.provider import LLMProvider


class Runtime:
    def __init__(
        self,
        artifact_root: Path,
        repo_root: Path,
        trace_root: Path | None = None,
        generated_root: Path | None = None,
        config: HarnessConfig | None = None,
    ) -> None:
        self.artifact_store = ArtifactStore(artifact_root)
        self.repository = Repository(repo_root)
        self.trace_store = TraceStore(trace_root) if trace_root else None
        if generated_root:
            generated_root.mkdir(parents=True, exist_ok=True)
        self._generated_root = generated_root
        self._agents: dict[str, Agent] = {}
        self._task_graph: dict[str, list[str]] = {}
        self._agent_registry: dict[str, type[Agent]] = {}
        self._agent_usage: dict[str, dict] = {}
        self._usage_locks: dict[str, asyncio.Lock] = {}
        self._llm: LLMProvider | None = None
        self._gitignore_filter: Callable[[str], bool] | None = None
        self._gitignore_mtime: float | None = None
        self._safety_max_iterations = config.safety.max_iterations if config else 500
        self._repeated_call_limit = config.safety.repeated_call_limit if config else 5

        self._report_handlers: list[Callable[[str, ReportPayload], None]] = []
        self._budget_handlers: list[Callable[[str, BudgetRequest], None]] = []
        self._escalation_handlers: list[Callable[[str, Escalation], None]] = []
        self._failure_handlers: list[Callable[[str, Failure], None]] = []
        self._activity_handlers: list[Callable[[ActivityEvent], None]] = []

        self.tool_registry = ToolRegistry()
        register_default_tools(self.tool_registry)

    @property
    def generated_root(self) -> Path | None:
        return self._generated_root

    def get_gitignore_filter(self) -> Callable[[str], bool]:
        gitignore = Path.cwd() / ".gitignore"
        mtime = gitignore.stat().st_mtime if gitignore.exists() else None
        if mtime and mtime == self._gitignore_mtime and self._gitignore_filter is not None:
            return self._gitignore_filter
        self._gitignore_mtime = mtime

        if not gitignore.exists():
            self._gitignore_filter = lambda p: False
            return self._gitignore_filter

        try:
            import pathspec
            spec = pathspec.PathSpec.from_lines(
                "gitignore", gitignore.read_text().splitlines()
            )
            self._gitignore_filter = spec.match_file
        except ImportError:
            self._gitignore_filter = lambda p: False
        return self._gitignore_filter

    def register_agent_class(self, name: str, cls: type[Agent]) -> None:
        self._agent_registry[name] = cls

    def set_llm(self, llm: LLMProvider | None) -> None:
        self._llm = llm

    def delegate(self, task: Task, parent: Agent | None = None, agent_type: str | None = None) -> Agent:
        agent_id = uuid4().hex[:12]
        if agent_type and agent_type in self._agent_registry:
            cls = self._agent_registry[agent_type]
            agent = cls(agent_id, task, self, parent, safety_max_iterations=self._safety_max_iterations, repeated_call_limit=self._repeated_call_limit)
        else:
            agent = Agent(agent_id, task, self, parent, safety_max_iterations=self._safety_max_iterations, repeated_call_limit=self._repeated_call_limit)
        self._agents[agent_id] = agent
        self._task_graph[agent_id] = []
        if parent:
            self._task_graph.setdefault(parent.id, []).append(agent_id)
        task.status = TaskStatus.running
        return agent

    def deliver_report(self, agent_id: str, payload: ReportPayload) -> None:
        agent = self._agents.get(agent_id)
        if not agent:
            return
        agent.task.status = TaskStatus.completed

        summary = payload.summary or ""
        lines = summary.split("\n", 1)
        headline = lines[0].strip()[:200]

        view = ArtifactView(
            headline=headline,
            summary_200=summary[:200],
            summary_1000=summary[:1000] if len(summary) > 200 else "",
            technical=payload.technical_summary or "",
            full_report=payload.full_report or "",
        )
        artifact = Artifact(task_id=agent.task.id, agent_id=agent_id, views=view)
        self.artifact_store.save(artifact)

        commit = Commit(
            task_id=agent.task.id,
            agent_id=agent_id,
            summary=payload.summary,
            artifact_ids=payload.artifact_ids + [artifact.id],
            parent_ids=[agent.task.parent_id] if agent.task.parent_id else [],
        )
        self.repository.commit(commit)

        for h in self._report_handlers:
            h(agent_id, payload)

    def deliver_budget_request(self, agent_id: str, req: BudgetRequest) -> None:
        for h in self._budget_handlers:
            h(agent_id, req)

    def deliver_escalation(self, agent_id: str, esc: Escalation) -> None:
        agent = self._agents.get(agent_id)
        if agent:
            agent.task.status = TaskStatus.escalated
        for h in self._escalation_handlers:
            h(agent_id, esc)

    def deliver_failure(self, agent_id: str, fail: Failure) -> None:
        agent = self._agents.get(agent_id)
        if agent:
            agent.task.status = TaskStatus.failed
        for h in self._failure_handlers:
            h(agent_id, fail)

    def on_report(self, handler: Callable[[str, ReportPayload], None]) -> None:
        self._report_handlers.append(handler)

    def on_budget_request(self, handler: Callable[[str, BudgetRequest], None]) -> None:
        self._budget_handlers.append(handler)

    def on_escalation(self, handler: Callable[[str, Escalation], None]) -> None:
        self._escalation_handlers.append(handler)

    def on_failure(self, handler: Callable[[str, Failure], None]) -> None:
        self._failure_handlers.append(handler)

    def on_activity(self, handler: Callable[[ActivityEvent], None]) -> None:
        self._activity_handlers.append(handler)

    def emit_activity(self, event: ActivityEvent) -> None:
        for h in self._activity_handlers:
            h(event)

    def get_agent(self, agent_id: str) -> Agent | None:
        return self._agents.get(agent_id)

    def task_graph(self) -> dict[str, list[str]]:
        return dict(self._task_graph)

    def agent_count(self) -> int:
        return len(self._agents)

    async def record_usage(self, agent_id: str, *, prompt_tokens: int = 0, completion_tokens: int = 0, message_count: int = 0) -> None:
        lock = self._usage_locks.setdefault(agent_id, asyncio.Lock())
        async with lock:
            prev = self._agent_usage.get(agent_id, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "message_count": 0})
            prev["prompt_tokens"] += prompt_tokens
            prev["completion_tokens"] += completion_tokens
            prev["total_tokens"] += prompt_tokens + completion_tokens
            prev["message_count"] = message_count
            self._agent_usage[agent_id] = prev

    def get_usage(self, agent_id: str) -> dict:
        return self._agent_usage.get(agent_id, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "message_count": 0})

    def total_usage(self) -> dict:
        total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        for u in self._agent_usage.values():
            total["prompt_tokens"] += u.get("prompt_tokens", 0)
            total["completion_tokens"] += u.get("completion_tokens", 0)
            total["total_tokens"] += u.get("total_tokens", 0)
        return total

    def reset(self, *, clear_handlers: bool = False) -> None:
        self._agents.clear()
        self._task_graph.clear()
        self._agent_usage.clear()
        self._usage_locks.clear()
        self._gitignore_filter = None
        self._gitignore_mtime = None
        self.repository.clear()
        self.artifact_store.clear()
        if self.trace_store:
            self.trace_store.clear()
        if clear_handlers:
            self._report_handlers.clear()
            self._budget_handlers.clear()
            self._escalation_handlers.clear()
            self._failure_handlers.clear()
            self._activity_handlers.clear()