from __future__ import annotations

import json
from abc import ABC
from typing import TYPE_CHECKING, Any

from .task import (
    BudgetRequest,
    Escalation,
    Failure,
    ReportPayload,
    Task,
)

if TYPE_CHECKING:
    from ..llm.provider import LLMProvider
    from .runtime import Runtime


AGENT_SYSTEM_PROMPT = """\
You are an agent in a recursive tool-calling harness.

## Your capabilities (available tools)

You have the following tools at your disposal. Call them by responding with
structured function calls in the format your LLM API supports.

- **read(path)**: Read a file from disk
- **write(path, content)**: Write content to a file
- **glob(pattern)**: List files matching a pattern (e.g. **/*.py)
- **webfetch(url)**: Fetch content from a URL
- **edit(path, old_string, new_string)**: Find and replace text in a file
- **spawn(description)**: Create a sub-agent to handle a subtask. This is
  how you decompose complex work. The sub-agent runs autonomously and
  returns its results when done.
- **ask(question)**: Ask the user a question and get their input. Use this
  when you need clarification, confirmation, or additional information.
- **report(summary, artifact_ids)**: Submit your final result and signal
  completion. Call this when your task is done.
- **escalate(issue)**: Ask your parent agent for help with a problem.
- **fail(error)**: Report a failure.

## How to work

1. Analyze your task description carefully.
2. If the task is complex, break it down by spawning sub-agents.
3. Use read/write/glob/webfetch/edit to gather information and produce output.
4. When your task is complete, call report() with a summary of findings.
5. If you encounter a problem you cannot solve, escalate() to your parent.

## Rules

- You do NOT know about siblings, cousins, or the global task graph.
- You see only your own task, your parent, and your children.
- Write important data to disk using write(); reference files by path.
- When you call spawn(), the sub-agent runs immediately and you receive its
  completion status. You do not need to await it separately.
"""


class Agent(ABC):
    def __init__(self, agent_id: str, task: Task, runtime: Runtime, parent: Agent | None = None) -> None:
        self.id = agent_id
        self.task = task
        self._runtime = runtime
        self.parent = parent
        self.children: list[Agent] = []

    @property
    def llm(self) -> LLMProvider | None:
        return self._runtime._llm

    @property
    def guidelines(self) -> str:
        return AGENT_SYSTEM_PROMPT

    async def run(self) -> None:
        llm = self.llm
        if not llm:
            self.report(ReportPayload(
                task_id=self.task.id,
                summary=f"Agent {self.id} executed: {self.task.description}",
            ))
            return

        tools = self._runtime.tool_registry.openai_schemas()
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": self.task.description},
        ]

        while True:
            response = await llm.generate_with_tools(messages, tools)

            if response.tool_calls:
                assistant_msg: dict[str, Any] = {"role": "assistant", "content": response.content or ""}
                assistant_msg["tool_calls"] = []
                results: list[dict[str, Any]] = []

                for tc in response.tool_calls:
                    assistant_msg["tool_calls"].append({
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    })
                    result = await self._runtime.tool_registry.execute(
                        tc.name, tc.id, agent=self, **tc.arguments
                    )
                    results.append({
                        "role": "tool",
                        "tool_call_id": result.tool_call_id,
                        "content": result.content,
                    })

                messages.append(assistant_msg)
                messages.extend(results)
            else:
                content = response.content or ""
                self.report(ReportPayload(
                    task_id=self.task.id,
                    summary=content,
                ))
                return

    def spawn(self, description: str, agent_type: str | None = None, **metadata: object) -> Agent:
        child_task = Task(description=description, parent_id=self.task.id, metadata=metadata)
        child = self._runtime.spawn_agent(child_task, parent=self, agent_type=agent_type)
        self.children.append(child)
        return child

    def report(self, payload: ReportPayload) -> None:
        self._runtime.deliver_report(self.id, payload)

    def request_more_budget(self, current_usage: int, requested: int, reason: str) -> None:
        req = BudgetRequest(task_id=self.task.id, current_usage=current_usage, requested=requested, reason=reason)
        self._runtime.deliver_budget_request(self.id, req)

    def escalate(self, issue: str, **context: object) -> None:
        e = Escalation(task_id=self.task.id, issue=issue, context=context)
        self._runtime.deliver_escalation(self.id, e)

    def fail(self, error: str, trace: str | None = None) -> None:
        f = Failure(task_id=self.task.id, error=error, trace=trace)
        self._runtime.deliver_failure(self.id, f)