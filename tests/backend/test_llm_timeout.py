from __future__ import annotations

import httpx
import pytest
from openai import APITimeoutError

from dynamic_harness.core.agent import Agent
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import Task, TaskStatus
from dynamic_harness.llm.provider import LLMProvider, ToolCallResponse


class _TimeoutLLM(LLMProvider):
    """Raises an API read timeout the first ``fail_calls`` generations, then
    completes normally. Mirrors the provider outage from the original crash."""

    def __init__(self, fail_calls: int) -> None:
        self.fail_calls = fail_calls
        self.calls = 0

    async def generate(self, system: str, user: str, config=None):
        raise NotImplementedError

    async def generate_with_tools(self, messages: list[dict], tools: list[dict], config=None):
        self.calls += 1
        if self.calls <= self.fail_calls:
            request = httpx.Request("POST", "http://provider.invalid/v1/chat/completions")
            raise APITimeoutError(request=request)
        return ToolCallResponse(content="done", model="mock")

    async def generate_structured(self, system, user, response_model, config=None):
        raise NotImplementedError


def test_timeout_classified_as_retryable() -> None:
    request = httpx.Request("POST", "http://provider.invalid/v1/chat/completions")
    # The `APITimeoutError` string message is "Request timed out." — the old
    # keyword matcher missed it; type-based classification must catch it.
    assert Agent._is_retryable(APITimeoutError(request=request)) is True


def test_plain_runtime_error_not_retryable() -> None:
    assert Agent._is_retryable(ValueError("bad request")) is False


@pytest.mark.asyncio
async def test_retries_transient_timeout_then_completes(runtime: Runtime) -> None:
    llm = _TimeoutLLM(fail_calls=2)
    runtime.set_llm(llm)
    runtime._self_heal_mode = False  # isolate plain retry behavior

    root = await runtime.run("do the thing")

    assert root.task.status == TaskStatus.completed
    assert root.last_report is not None
    assert llm.calls == 3  # two timeouts absorbed by retry + one success


@pytest.mark.asyncio
async def test_persistent_timeout_fails_gracefully(runtime: Runtime) -> None:
    runtime._self_heal_mode = False
    llm = _TimeoutLLM(fail_calls=10_000)
    runtime.set_llm(llm)

    # Must not raise/crash even after retries are exhausted.
    root = await runtime.run("do the thing")

    assert root.task.status == TaskStatus.failed
    assert root.last_failure is not None


@pytest.mark.asyncio
async def test_interactive_resume_converts_timeout_to_failure(runtime: Runtime) -> None:
    """The REPL resume path (continue_with_input) previously bypassed the error
    safety-net in run() and crashed the whole process on an LLM timeout."""
    runtime._self_heal_mode = False
    llm = _TimeoutLLM(fail_calls=10_000)
    runtime.set_llm(llm)

    task = runtime.delegate(Task(description="interactive task"))
    await task.run()  # first run fails gracefully
    assert task.last_failure is not None
    calls_after_first_run = llm.calls

    # Resume path must not raise; it converts the outage into a failure.
    await task.continue_with_input("keep going")

    assert task.last_failure is not None
    assert llm.calls > calls_after_first_run
