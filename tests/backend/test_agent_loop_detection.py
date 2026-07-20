from __future__ import annotations

import pytest

from dynamic_harness.core.agent import Agent
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import Task, TaskStatus
from dynamic_harness.llm.provider import LLMProvider, ToolCallData, ToolCallResponse


class _LoopToolLLM(LLMProvider):
    """Returns the same tool call every time to simulate a stuck agent."""

    def __init__(self, tool_name: str = "write", tool_args: dict | None = None, max_calls: int | None = None) -> None:
        self.tool_name = tool_name
        self.tool_args = tool_args or {"path": "/workspace/greeting.txt", "content": "hello"}
        self.max_calls = max_calls
        self.call_count = 0

    async def generate(self, system: str, user: str, config=None):
        raise NotImplementedError

    async def generate_with_tools(self, messages: list[dict], tools: list[dict], config=None):
        self.call_count += 1
        if self.max_calls is not None and self.call_count > self.max_calls:
            return ToolCallResponse(content="done", model="mock")
        return ToolCallResponse(
            content=None,
            model="mock",
            tool_calls=[
                ToolCallData(
                    id=f"call_{self.call_count}",
                    name=self.tool_name,
                    arguments=dict(self.tool_args),
                )
            ],
        )

    async def generate_structured(self, system: str, user: str, response_model, config=None):
        raise NotImplementedError


def _make_agent(
    runtime: Runtime,
    task: Task,
    safety_max_iterations: int = 50,
    repeated_call_limit: int = 5,
) -> Agent:
    agent = Agent("test-agent", task, runtime, safety_max_iterations=safety_max_iterations, repeated_call_limit=repeated_call_limit)
    task.status = TaskStatus.running
    runtime._agents[agent.id] = agent
    return agent


@pytest.mark.asyncio
async def test_safety_max_iterations_limit_reached(runtime: Runtime) -> None:
    llm = _LoopToolLLM()
    runtime.set_llm(llm)

    root = _make_agent(runtime, Task(description="Looping task"), safety_max_iterations=5, repeated_call_limit=10)

    await root.run()

    assert root.task.status.value == "failed"


@pytest.mark.asyncio
async def test_repeated_identical_calls_trigger_safety(runtime: Runtime) -> None:
    llm = _LoopToolLLM()
    runtime.set_llm(llm)

    root = _make_agent(runtime, Task(description="Looping task"), safety_max_iterations=100, repeated_call_limit=3)

    await root.run()

    assert root.task.status.value == "failed"


@pytest.mark.asyncio
async def test_completes_when_tool_llm_finishes(runtime: Runtime) -> None:
    call_seq = [
        {"path": "/a.txt", "content": "1"},
        {"path": "/b.txt", "content": "2"},
    ]

    class VaryingToolLLM(LLMProvider):
        def __init__(self):
            self.idx = 0

        async def generate(self, system, user, config=None):
            raise NotImplementedError

        async def generate_with_tools(self, messages, tools, config=None):
            if self.idx >= len(call_seq):
                return ToolCallResponse(content="done", model="mock")
            args = call_seq[self.idx]
            self.idx += 1
            return ToolCallResponse(
                content=None,
                model="mock",
                tool_calls=[ToolCallData(id=f"call_{self.idx}", name="write", arguments=args)],
            )

        async def generate_structured(self, system, user, response_model, config=None):
            raise NotImplementedError

    llm = VaryingToolLLM()
    runtime.set_llm(llm)

    root = _make_agent(runtime, Task(description="Varying task"))

    await root.run()

    assert root.task.status.value == "completed"


@pytest.mark.asyncio
async def test_completes_normally_with_small_number_of_calls(runtime: Runtime) -> None:
    llm = _LoopToolLLM(max_calls=2)
    runtime.set_llm(llm)

    root = _make_agent(runtime, Task(description="Normal task"))

    await root.run()

    assert root.task.status.value == "completed"
