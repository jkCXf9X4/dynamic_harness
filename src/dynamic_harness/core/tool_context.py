"""ToolContext — the narrow, public interface tools receive.

Tools no longer receive the whole ``Agent``; the run loop hands them a
``ToolContext`` exposing only the actions a tool is allowed to perform. This
keeps the actor boundary real: a tool cannot reach into agent/runtime private
state because none of it is exposed here.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from .task import ActivityEvent, ReportPayload

if TYPE_CHECKING:
    from .agent import Agent


class ToolContext:
    """Public capability façade over an agent, provided to tool functions."""

    def __init__(self, agent: Agent) -> None:
        self._agent = agent

    @property
    def task_id(self) -> str:
        return self._agent.task.id

    @property
    def agent_id(self) -> str:
        return self._agent.id

    # -- environment -----------------------------------------------------

    @property
    def generated_root(self) -> Any:
        return self._agent.generated_root

    def gitignore_filter(self):
        return self._agent.get_gitignore_filter()

    async def workspace_lock(self, path: str) -> asyncio.Lock:
        return await self._agent.workspace_lock(path)

    def repo_lock(self) -> asyncio.Lock:
        return self._agent.repo_lock()

    # -- read / context observation --------------------------------------

    @property
    def llm(self):
        return self._agent.llm

    @property
    def messages(self) -> list[dict[str, Any]]:
        """Read-only snapshot of the agent's current message buffer."""
        return list(self._agent.context.messages)

    @property
    def message_count(self) -> int:
        return self._agent.message_count

    @property
    def artifact_store(self) -> Any:
        return self._agent.artifact_store

    def latest_assistant_message(self, agent_id: str) -> str:
        """Latest assistant text from another agent (empty if none)."""
        agent = self._agent.get_other_agent(agent_id)
        return agent.latest_assistant_message() if agent is not None else ""

    # -- context management ----------------------------------------------

    def set_plan(self, *, steps=None, objective=None, acceptance=None, deliverable=None) -> str:
        return self._agent.set_plan(
            steps=steps, objective=objective, acceptance=acceptance, deliverable=deliverable,
        )

    def checkpoint(self, note: str) -> str:
        return self._agent.checkpoint(note)

    async def compress(self) -> dict[str, Any]:
        compression_prompt = "\n".join([
            "You are a context compression engine. Condense the following agent",
            "conversation into a single concise paragraph. Preserve:",
            "- The original task and goals",
            "- Key findings, decisions, and code changes",
            "- Open questions and unresolved issues",
            "- Current state and next steps",
            "Output ONLY the summary paragraph, no preamble.",
        ])
        return await self._agent.context.compress(self.llm, compression_prompt)

    def prune(self, prune_ids) -> dict[str, Any] | None:
        return self._agent.context.prune(prune_ids)

    def restore(self, prune_id: str) -> str:
        return self._agent.context.restore(prune_id)

    # -- actions ---------------------------------------------------------

    def emit_activity(self, event: ActivityEvent) -> None:
        self._agent.emit_activity(event)

    async def run_delegate_tool(
        self,
        description: str,
        *,
        role: str | None = None,
        system_prompt: str | None = None,
        agent_type: str | None = None,
        tool_call_id: str = "",
    ) -> str:
        return await self._agent.run_delegate_tool(
            description, role=role, system_prompt=system_prompt,
            agent_type=agent_type, tool_call_id=tool_call_id,
        )

    def report(self, payload: ReportPayload) -> None:
        self._agent.report(payload)

    def escalate(self, issue: str, **context: Any) -> None:
        self._agent.escalate(issue, **context)

    def fail(self, error: str, trace: str | None = None) -> None:
        self._agent.fail(error, trace=trace)

    def get_other_agent(self, agent_id: str) -> Any:
        return self._agent.get_other_agent(agent_id)

    async def continue_with_input(self, agent_id: str, message: str) -> None:
        """Resume another agent with a new message (used by ``converse``)."""
        target = self._agent.get_other_agent(agent_id)
        if target is not None:
            await target.continue_with_input(message)
