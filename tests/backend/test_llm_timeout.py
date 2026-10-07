from __future__ import annotations

import httpx
import pytest
from openai import APITimeoutError, InternalServerError, RateLimitError

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


class _UpstreamServerLLM(LLMProvider):
    """Raises an upstream 5xx (openai ``InternalServerError``) the first
    ``fail_calls`` generations, then completes normally. Mirrors the upstream
    500 / 502 provider outages that surfaced as "Unhandled agent error"."""

    def __init__(self, fail_calls: int, status: int, message: str) -> None:
        self.fail_calls = fail_calls
        self.status = status
        self.message = message
        self.calls = 0

    async def generate(self, system: str, user: str, config=None):
        raise NotImplementedError

    async def generate_with_tools(self, messages: list[dict], tools: list[dict], config=None):
        self.calls += 1
        if self.calls <= self.fail_calls:
            raise _server_error(self.status, self.message)
        return ToolCallResponse(content="done", model="mock")

    async def generate_structured(self, system, user, response_model, config=None):
        raise NotImplementedError


def _server_error(status: int, message: str) -> InternalServerError:
    """An openai ``InternalServerError`` rendered exactly as the SDK surfaces
    provider 5xx responses ("Error code: <status> - {body}")."""
    request = httpx.Request("POST", "http://provider.invalid/v1/chat/completions")
    body = {
        "error": {
            "type": "internal_server_error",
            "code": None,
            "message": message,
            "param": None,
        }
    }
    return InternalServerError(
        message=f"Error code: {status} - {body}",
        response=httpx.Response(status, request=request),
        body=body,
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


def test_upstream_server_errors_classified_as_retryable() -> None:
    # The exact provider messages from the field: an upstream 500 and a 502
    # bad_gateway. Type-based classification (InternalServerError) must catch
    # both; they are generic transient failures, not rate limits.
    for status, message in (
        (500, "Failed to communicate with the upstream service."),
        (502, "Could not connect to the gateway. Try again later."),
    ):
        exc = _server_error(status, message)
        assert "Error code:" in str(exc)  # SDK-rendered 5xx
        assert Agent._is_retryable(exc) is True
        assert Agent._is_rate_limit(exc) is False


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
async def test_retries_upstream_500_then_completes(runtime: Runtime) -> None:
    """A transient upstream 500 ("Failed to communicate with the upstream
    service.") is absorbed by the generic retry budget."""
    runtime._self_heal_mode = False
    llm = _UpstreamServerLLM(
        fail_calls=2, status=500,
        message="Failed to communicate with the upstream service.",
    )
    runtime.set_llm(llm)

    root = runtime.delegate(Task(description="do the thing"))
    _no_sleep(root)
    await root.run()

    assert root.task.status == TaskStatus.completed
    assert root.last_report is not None
    assert llm.calls == 3  # two 500s absorbed by retry + one success


@pytest.mark.asyncio
async def test_retries_upstream_502_bad_gateway_then_completes(runtime: Runtime) -> None:
    """A 502 bad_gateway ("Could not connect to the gateway. Try again
    later.") is retried like any other transient server error."""
    runtime._self_heal_mode = False
    llm = _UpstreamServerLLM(
        fail_calls=3, status=502,
        message="Could not connect to the gateway. Try again later.",
    )
    runtime.set_llm(llm)

    root = runtime.delegate(Task(description="do the thing"))
    _no_sleep(root)
    await root.run()

    assert root.task.status == TaskStatus.completed
    assert root.last_report is not None
    assert llm.calls == 4  # three 502s absorbed by retry + one success


@pytest.mark.asyncio
async def test_persistent_upstream_500_fails_gracefully(runtime: Runtime) -> None:
    """A 500 that outlasts the generic retry budget fails after exactly four
    attempts, and the failure says so instead of reading as never-retried."""
    runtime._self_heal_mode = False
    llm = _UpstreamServerLLM(
        fail_calls=10_000, status=500,
        message="Failed to communicate with the upstream service.",
    )
    runtime.set_llm(llm)

    root = runtime.delegate(Task(description="do the thing"))
    _no_sleep(root)
    await root.run()

    assert root.task.status == TaskStatus.failed
    assert root.last_failure is not None
    assert llm.calls == 4  # exhausted exactly the generic budget
    assert "LLM call failed after 4 attempt(s)" in root.last_failure.error
    assert "transient retry budget exhausted" in root.last_failure.error


class _ScheduledOutageLLM(LLMProvider):
    """Fails each of the first ``len(schedule)`` generations with the matching
    (status, message) 5xx, then completes normally. Lets one agent lifetime
    stage two different outages — e.g. a 500 retry-budget exhaustion on the
    first run, then a 502 on the user continuation."""

    def __init__(self, schedule: list[tuple[int, str]]) -> None:
        self.schedule = list(schedule)
        self.calls = 0

    async def generate(self, system: str, user: str, config=None):
        raise NotImplementedError

    async def generate_with_tools(self, messages: list[dict], tools: list[dict], config=None):
        self.calls += 1
        if self.schedule:
            status, message = self.schedule.pop(0)
            raise _server_error(status, message)
        return ToolCallResponse(content="done", model="mock")

    async def generate_structured(self, system, user, response_model, config=None):
        raise NotImplementedError


@pytest.mark.asyncio
async def test_continued_root_recovers_from_upstream_outage(runtime: Runtime) -> None:
    """A root that failed on an exhausted retry budget recovers when the user
    continues it with a new message once the upstream is back."""
    runtime._self_heal_mode = False
    llm = _ScheduledOutageLLM(
        [(500, "Failed to communicate with the upstream service.")] * 4
    )
    runtime.set_llm(llm)

    root = runtime.delegate(Task(description="do the thing"))
    _no_sleep(root)
    await root.run()  # first run: generic retry budget exhausted → failed
    assert root.task.status == TaskStatus.failed
    assert "LLM call failed after 4 attempt(s)" in root.last_failure.error

    await root.continue_with_input("the upstream is back — try again")

    assert root.task.status == TaskStatus.completed
    assert root.last_report is not None
    assert llm.calls == 5  # four exhausted attempts + one success


@pytest.mark.asyncio
async def test_continued_root_remarks_failed_when_outage_repeats(runtime: Runtime) -> None:
    """If the outage repeats on the continuation, the fresh failure must replace
    the stale one and re-mark the task failed — not leave the root in "running"
    limbo while every view keeps showing the old error."""
    runtime._self_heal_mode = False
    llm = _ScheduledOutageLLM(
        [(500, "Failed to communicate with the upstream service.")] * 4
        + [(502, "Could not connect to the gateway. Try again later.")] * 4
    )
    runtime.set_llm(llm)

    root = runtime.delegate(Task(description="do the thing"))
    _no_sleep(root)
    await root.run()
    assert root.task.status == TaskStatus.failed
    assert "Error code: 500" in root.last_failure.error

    await root.continue_with_input("try again now")

    assert root.task.status == TaskStatus.failed  # re-marked, not "running"
    assert "Error code: 502" in root.last_failure.error  # fresh, not stale
    assert "LLM call failed after 4 attempt(s)" in root.last_failure.error
    assert llm.calls == 8  # two full generic budgets, one per turn


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
