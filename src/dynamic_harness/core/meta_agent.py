from __future__ import annotations

from ..core.agent import AGENT_SYSTEM_PROMPT, Agent
from ..core.runtime import Runtime
from ..core.task import Task

META_AGENT_PROMPT = AGENT_SYSTEM_PROMPT + """

## Additional guidance

You are a meta-agent. When you encounter a task that requires specialist
knowledge, use the `spawn()` tool to create sub-agents. You do NOT need
to generate custom Python code — the same tool loop applies to all agents.
Your job is to plan, decompose, delegate, and synthesize.
"""


class MetaAgent(Agent):
    def __init__(
        self,
        agent_id: str,
        task: Task,
        runtime: Runtime,
        parent: Agent | None = None,
    ) -> None:
        super().__init__(agent_id, task, runtime, parent)

    @property
    def guidelines(self) -> str:
        return META_AGENT_PROMPT

    async def run(self) -> None:
        await super().run()