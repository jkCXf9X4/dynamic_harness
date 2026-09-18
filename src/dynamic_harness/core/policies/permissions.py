"""Tool-permission policy as a composable policy object.

The role-based tool allow-list and the per-status eligibility gates (which
agent states are killable / conversable / resumable) were scattered across the
registry and the agent/runtime. This policy owns those decisions so a plugin
host exposing the same tools applies identical permissions without importing a
runtime.

Pure set/string logic: it decides *whether* an action is permitted and what to
say when refused; the caller performs the mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..task import TaskStatus


class ToolPermissionPolicy:
    """Role tool-gating + agent-state eligibility.

    Host-agnostic: an MCP tool-server host reuses the same allow-list and state
    gates so its surfaced tools behave like the harness's.
    """

    #: Tools an orchestrator IS allowed: orchestration + verification + its own
    #: context management (compress/prune/restore only manage its own memory).
    #: Anything else (read/write/glob/grep/edit/bash/webfetch) is worker work
    #: that an orchestrator physically cannot invoke — closing the "what counts
    #: as work" loophole in code, not just in prompt text.
    ORCHESTRATOR_ALLOWED_TOOLS: frozenset[str] = frozenset({
        "delegate", "converse", "kill", "status", "resume", "ask", "read_artifact", "usage",
        "report", "escalate", "fail",
        "compress", "prune", "restore",
        "plan", "checkpoint",
        "result_read",
        # Communication layer: coordination, not hands-on work.
        "post", "channel_read", "channels", "channel_info",
        "subscribe", "unsubscribe", "message",
    })

    ROLE_TOOL_OVERRIDES: dict[str, frozenset[str]] = {
        "orchestrator": ORCHESTRATOR_ALLOWED_TOOLS,
    }

    #: Agent states that may be killed (already-terminal agents are exempt: a
    #: kill must not create a spurious Failure record over a finished report).
    KILLABLE_STATUSES: frozenset[str] = frozenset({"pending", "running"})

    #: Agent states that may receive a ``converse`` message.
    CONVERSABLE_STATUSES: frozenset[str] = frozenset({"completed", "running"})

    #: Agent states that the parent ``resume`` tool may recover.
    RESUMABLE_STATUSES: frozenset[str] = frozenset({"failed", "completed"})

    # -- role gating -------------------------------------------------------

    @staticmethod
    def tools_for_role(role: str | None) -> frozenset[str] | None:
        """Explicit allow-list for a role, or None for no restriction."""
        if role is None:
            return None
        return ToolPermissionPolicy.ROLE_TOOL_OVERRIDES.get(role)

    @classmethod
    def tool_allowed(cls, role: str | None, name: str) -> bool:
        allowed = cls.tools_for_role(role)
        return allowed is None or name in allowed

    @classmethod
    def role_refusal(cls, role: str | None, name: str) -> str | None:
        """The message a refused tool call should return, or None if allowed."""
        allowed = cls.tools_for_role(role)
        if allowed is None or name in allowed:
            return None
        return (
            f"Error: tool '{name}' is not allowed for role "
            f"'{role}'. Orchestrators may only use: "
            f"{', '.join(sorted(allowed))}. Delegate this work instead."
        )

    # -- agent-state eligibility -------------------------------------------

    @classmethod
    def killable(cls, status: "TaskStatus") -> bool:
        return status.value in cls.KILLABLE_STATUSES

    @classmethod
    def conversable(cls, status: "TaskStatus") -> bool:
        return status.value in cls.CONVERSABLE_STATUSES

    @classmethod
    def resumable(cls, status: "TaskStatus") -> bool:
        return status.value in cls.RESUMABLE_STATUSES


@dataclass(frozen=True)
class EligibilityVerdict:
    """Whether an actor may perform an action on an agent, with the refusal."""

    allowed: bool
    message: str | None = None