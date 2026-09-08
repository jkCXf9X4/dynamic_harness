from __future__ import annotations

import httpx
import pytest
from openai import APITimeoutError, RateLimitError

from dynamic_harness.core import agent as agent_mod
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
        self.configs: list = []

    async def generate(self, system: str, user: str, config=None):
        raise NotImplementedError

    async def generate_with_tools(self, messages: list[dict], tools: list[dict], config=None):
        self.calls += 1
        self.configs.append(config)
        if self.calls <= self.fail_calls:
            request = httpx.Request("POST", "http://provider.invalid/v1/chat/completions")
            raise APITimeoutError(request=request)
        return ToolCallResponse(content="done", model="mock")

    async def generate_structured(self, system, user, response_model, config=None):
        raise NotImplementedError


class _RateLimitLLM(LLMProvider):
    """Raises an HTTP 429 the first ``fail_calls`` generations, then completes
    normally. Records the LLMConfig each call so tests can watch the
    session-pin / provider-fallback behavior."""

    def __init__(self, fail_calls: int) -> None:
        self.fail_calls = fail_calls
        self.calls = 0
        self.configs: list = []

    async def generate(self, system: str, user: str, config=None):
        raise NotImplementedError

    async def generate_with_tools(self, messages: list[dict], tools: list[dict], config=None):
        self.calls += 1
        self.configs.append(config)
        if self.calls <= self.fail_calls:
            request = httpx.Request("POST", "http://provider.invalid/v1/chat/completions")
            raise RateLimitError(
                message="Error code: 429 - engine_overloaded",
                response=httpx.Response(429, request=request),
                body=None,
            )
        return ToolCallResponse(content="done", model="mock")

    async def generate_structured(self, system, user, response_model, config=None):
        raise NotImplementedError


def _rate_limit_error(**headers: str) -> RateLimitError:
    request = httpx.Request("POST", "http://provider.invalid/v1/chat/completions")
    return RateLimitError(
        message="Error code: 429 - rate limited",
        response=httpx.Response(429, request=request, headers=dict(headers)),
        body=None,
    )


def _no_sleep(root: Agent) -> None:
    """Kill the retry backoff so budget-exhaustion tests run instantly."""
    root.retry_base_delay_seconds = 0.0
    root.retry_jitter_seconds = 0.0


def test_timeout_classified_as_retryable() -> None:
    request = httpx.Request("POST", "http://provider.invalid/v1/chat/completions")
    # The `APITimeoutError` string message is "Request timed out." — the old
    # keyword matcher missed it; type-based classification must catch it.
    assert Agent._is_retryable(APITimeoutError(request=request)) is True


def test_rate_limit_classified_as_retryable() -> None:
    exc = _rate_limit_error()
    # Type-based classification must catch it regardless of message text.
    assert Agent._is_retryable(exc) is True


def test_plain_runtime_error_not_retryable() -> None:
    assert Agent._is_retryable(ValueError("bad request")) is False


def test_rate_limit_versus_timeout_classification() -> None:
    request = httpx.Request("POST", "http://provider.invalid/v1/chat/completions")
    assert Agent._is_rate_limit(_rate_limit_error()) is True
    assert Agent._is_rate_limit(APITimeoutError(request=request)) is False
    assert Agent._is_rate_limit(ValueError("429")) is True  # keyword fallback
    assert Agent._is_rate_limit(ValueError("bad request")) is False


def test_retry_after_header_parsed() -> None:
    exc = _rate_limit_error(**{"retry-after": "12"})
    assert Agent._retry_after_seconds(exc) == 12.0
    # No response / no header / non-numeric → None (falls back to the backoff).
    assert Agent._retry_after_seconds(ValueError("no response")) is None
    assert Agent._retry_after_seconds(_rate_limit_error()) is None
    assert Agent._retry_after_seconds(_rate_limit_error(**{"retry-after": "later"})) is None


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

    root = await runtime.run("do the thing")

    # Must not raise/crash even after retries are exhausted.
    assert root.task.status == TaskStatus.failed
    assert root.last_failure is not None


@pytest.mark.asyncio
async def test_rate_limit_gets_larger_retry_budget(runtime: Runtime) -> None:
    """A rate limit is retried more aggressively than a generic failure: 5
    429s must be absorbed (budget 6) where the 4-attempt timeout budget would
    have already given up."""
    runtime._self_heal_mode = False
    llm = _RateLimitLLM(fail_calls=5)
    runtime.set_llm(llm)

    root = runtime.delegate(Task(description="do the thing"))
    _no_sleep(root)
    await root.run()

    assert root.task.status == TaskStatus.completed
    assert root.last_report is not None
    assert llm.calls == 6  # five rate limits absorbed by retry + one success


@pytest.mark.asyncio
async def test_persistent_rate_limit_fails_gracefully(runtime: Runtime) -> None:
    runtime._self_heal_mode = False
    llm = _RateLimitLLM(fail_calls=10_000)
    runtime.set_llm(llm)

    root = runtime.delegate(Task(description="do the thing"))
    _no_sleep(root)
    await root.run()

    assert root.task.status == TaskStatus.failed
    assert root.last_failure is not None
    assert llm.calls == 6  # exhausted exactly the rate-limit budget


@pytest.mark.asyncio
async def test_rate_limit_drops_session_pin_on_retry(runtime: Runtime) -> None:
    """Rate-limited retries unpin the session so OpenRouter can route to a
    provider that is not overloaded; the original (happy-path) pin is kept."""
    runtime._self_heal_mode = False
    llm = _RateLimitLLM(fail_calls=3)
    runtime.set_llm(llm)

    root = runtime.delegate(Task(description="do the thing"))
    _no_sleep(root)
    await root.run()

    assert root.task.status == TaskStatus.completed
    assert llm.configs[0].session_id is not None       # first call pinned
    assert all(c.session_id is None for c in llm.configs[1:])  # retries unpinned


@pytest.mark.asyncio
async def test_timeout_retries_keep_session_pin(runtime: Runtime) -> None:
    """Non-rate-limit retries do not unpin the session — prompt-cache warmth is
    only sacrificed for overloaded-provider routing."""
    runtime._self_heal_mode = False
    llm = _TimeoutLLM(fail_calls=2)
    runtime.set_llm(llm)

    root = runtime.delegate(Task(description="do the thing"))
    _no_sleep(root)
    await root.run()

    assert root.task.status == TaskStatus.completed
    assert all(c.session_id is not None for c in llm.configs)


@pytest.mark.asyncio
async def test_fallback_on_rate_limit_can_be_disabled(runtime: Runtime) -> None:
    runtime._self_heal_mode = False
    llm = _RateLimitLLM(fail_calls=2)
    runtime.set_llm(llm)

    root = runtime.delegate(Task(description="do the thing"))
    root.fallback_on_rate_limit = False
    _no_sleep(root)
    await root.run()

    assert root.task.status == TaskStatus.completed
    assert all(c.session_id is not None for c in llm.configs)


@pytest.mark.asyncio
async def test_rate_limit_backoff_scales_exponentially_and_caps(runtime: Runtime, monkeypatch) -> None:
    """Rate-limited backoff is base * multiplier * 2^n, honoring a provider
    Retry-After and capped at retry_max_delay_seconds."""
    sleeps: list[float] = []

    async def _fake_sleep(delay, result=None):
        sleeps.append(delay)
        return result

    monkeypatch.setattr(agent_mod.asyncio, "sleep", _fake_sleep)
    assert agent_mod.asyncio.sleep is _fake_sleep

    runtime._self_heal_mode = False
    llm = _RateLimitLLM(fail_calls=4)
    runtime.set_llm(llm)

    root = runtime.delegate(Task(description="do the thing"))
    root.retry_base_delay_seconds = 1.0
    root.rate_limit_backoff_multiplier = 3.0
    root.retry_max_delay_seconds = 7.0
    root.retry_jitter_seconds = 0.0
    root.fallback_on_rate_limit = False
    await root.run()

    # 4 rate-limited calls → 4 backoffs: 1*3*2^0=3, 1*3*2^1=6,
    # 1*3*2^2=12→capped at 7, then 7 again (already at the cap).
    assert sleeps == [3.0, 6.0, 7.0, 7.0]


class _RetryAfterLLM(LLMProvider):
    """Always fails with an HTTP 429 carrying a Retry-After header."""

    def __init__(self, retry_after: str) -> None:
        self.retry_after = retry_after

    async def generate(self, system: str, user: str, config=None):
        raise NotImplementedError

    async def generate_with_tools(self, messages: list[dict], tools: list[dict], config=None):
        raise _rate_limit_error(**{"retry-after": self.retry_after})

    async def generate_structured(self, system, user, response_model, config=None):
        raise NotImplementedError


@pytest.mark.asyncio
async def test_retry_after_header_extends_backoff(runtime: Runtime, monkeypatch) -> None:
    """A provider Retry-After beats the computed backoff when it is longer."""
    sleeps: list[float] = []

    async def _fake_sleep(delay, result=None):
        sleeps.append(delay)
        return result

    monkeypatch.setattr(agent_mod.asyncio, "sleep", _fake_sleep)

    runtime._self_heal_mode = False
    runtime.set_llm(_RetryAfterLLM(retry_after="25"))

    root = runtime.delegate(Task(description="do the thing"))
    root.retry_base_delay_seconds = 1.0
    root.rate_limit_backoff_multiplier = 3.0
    root.retry_max_delay_seconds = 30.0
    root.retry_jitter_seconds = 0.0
    root.fallback_on_rate_limit = False
    await root.run()

    # Retry-After extends every backoff until the exponential climb
    # overtakes it: 25, 25, 25, 25, then 30 (the cap on the 5th retry).
    assert sleeps == [25.0, 25.0, 25.0, 25.0, 30.0]


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
