from __future__ import annotations

from ..core.agent import Agent
from ..core.runtime import Runtime
from ..core.task import ReportPayload, Task
from ..llm.provider import LLMProvider


class ResearchAgent(Agent):
    def __init__(
        self,
        agent_id: str,
        task: Task,
        runtime: Runtime,
        parent: Agent | None = None,
        llm: LLMProvider | None = None,
    ) -> None:
        super().__init__(agent_id, task, runtime, parent)
        self.llm = llm

    async def run(self) -> None:
        try:
            result = await self._execute()
            self.report(result)
        except Exception as e:
            self.fail(str(e))

    async def _execute(self) -> ReportPayload:
        if self.llm:
            system = "You are a research agent. Respond with a structured summary of your findings."
            user = f"Task: {self.task.description}"
            resp = await self.llm.generate(system, user)
            return ReportPayload(
                task_id=self.task.id,
                summary=resp.content,
                claims=[resp.content[:200]],
                next_actions=[],
            )
        return ReportPayload(
            task_id=self.task.id,
            summary=f"Simulated research result for: {self.task.description}",
            claims=[f"Claim about {self.task.description[:50]}"],
            next_actions=[],
        )


class PlannerAgent(Agent):
    def __init__(
        self,
        agent_id: str,
        task: Task,
        runtime: Runtime,
        parent: Agent | None = None,
        llm: LLMProvider | None = None,
    ) -> None:
        super().__init__(agent_id, task, runtime, parent)
        self.llm = llm

    async def run(self) -> None:
        try:
            subtasks = await self._decompose()
            children = [self.spawn(desc) for desc in subtasks]
            for child in children:
                await child.run()
            merged = await self._merge()
            self.report(merged)
        except Exception as e:
            self.fail(str(e))

    async def _decompose(self) -> list[str]:
        if self.llm:
            system = "You are a planner. Break down the given task into 3-5 subtasks. Return each subtask as a separate line."
            user = f"Task: {self.task.description}"
            resp = await self.llm.generate(system, user)
            return [line.strip() for line in resp.content.strip().split("\n") if line.strip()]
        return [
            f"Research subtask 1 for: {self.task.description}",
            f"Research subtask 2 for: {self.task.description}",
        ]

    async def _merge(self) -> ReportPayload:
        summaries: list[str] = []
        for child in self.children:
            summaries.append(f"Result from {child.id}: {child.task.description}")
        return ReportPayload(
            task_id=self.task.id,
            summary="\n".join(summaries),
            next_actions=[],
        )