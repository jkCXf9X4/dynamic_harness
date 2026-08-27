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

    def usage_summary(self) -> dict[str, Any]:
        """Live cumulative usage + context state for this agent.

        Cache-clean feedback: the agent calls the tool to read its own counters
        rather than the runtime appending a changing per-turn observation message
        (which would zero the provider prompt cache). Callers shouldn't inspect
        private agent state; this centralizes the reading here on ToolContext.
        """
        agent = self._agent
        u = agent._runtime.get_usage(agent.id)
        return {
            "agent_id": agent.id,
            "iteration": getattr(agent, "_iteration", 0),
            "messages_in_context": agent.message_count,
            "cumulative_messages_sent": u.get("message_count", 0),
            "cumulative_prompt_tokens": u.get("prompt_tokens", 0),
            "cumulative_completion_tokens": u.get("completion_tokens", 0),
            "cumulative_total_tokens": u.get("total_tokens", 0),
            "cumulative_cached_tokens": u.get("cached_tokens", 0),
            "live_context_token_estimate": agent.context.estimate_prompt_tokens(),
            "max_agent_tokens": agent.max_agent_tokens,
        }

    @property
    def artifact_store(self) -> Any:
        return self._agent.artifact_store

    def record_archived_artifact(self, artifact_id: str) -> None:
        """Track an artifact this agent archived mid-run (via the `archive` tool).
        These ids are linked into the agent's final report commit so temp/working
        artifacts show up in repository provenance, not just the artifact index.
        """
        self._agent._archived_artifact_ids.append(artifact_id)

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

    async def kill(
        self,
        agent_id: str,
        *,
        reason: str | None = None,
        recursive: bool = False,
    ) -> str:
        """Kill a child agent: cancel its in-flight work and mark it failed."""
        return await self._agent.kill(
            agent_id, reason=reason, recursive=recursive,
        )

    async def resume_child(
        self,
        agent_id: str,
        *,
        note: str | None = None,
        strategy: str = "automatic",
    ) -> str:
        """Resume a failed/under-delivered child agent (see ``Agent.resume_child``)."""
        return await self._agent.resume_child(
            agent_id, note=note, strategy=strategy,
        )

    async def status(self, agent_id: str | None = None) -> str:
        """Snapshot child status(es) + partial progress.

        With ``agent_id``: the snapshot of that (direct) child. Without: a list
        of snapshots for every child this agent delegated. Each snapshot carries
        the child's status/outcome, final summary (or failure reason), artifact,
        its plan (done + pending steps) and recent in-context progress, so the
        caller can salvage partial data and retry a dead child."""
        import json
        if agent_id:
            child = self._agent.get_other_agent(agent_id)
            if child is None:
                return json.dumps({"error": f"no agent found with ID {agent_id}"})
            if child.parent is not self._agent:
                return json.dumps({
                    "error": f"agent {agent_id} is not one of your direct "
                             "children; you may only read status of agents you "
                             "delegated",
                })
            return json.dumps(child.runtime_snapshot(), indent=2)
        snapshots = [
            c.runtime_snapshot() for c in self._agent.children
        ]
        return json.dumps(snapshots, indent=2)

    async def continue_with_input(self, agent_id: str, message: str) -> None:
        """Resume another agent with a new message (used by ``converse``)."""
        target = self._agent.get_other_agent(agent_id)
        if target is not None:
            await target.continue_with_input(message)
