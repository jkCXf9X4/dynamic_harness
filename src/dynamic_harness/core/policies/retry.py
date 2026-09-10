"""LLM call retry policy as a composable policy object.

The per-failure-class retry decisions that ``Agent._llm_call_with_retry``
used to embed inline live here as a standalone policy: classification of an
exception as retryable / rate-limited, the exponentially-growing backoff
formula (scaled for rate limits, honoring a provider ``Retry-After`` header,
capped at ``retry_max_delay_seconds``), and the session-pin-drop rule that
lets OpenRouter route rate-limited retries off an overloaded upstream pool.

The policy is a pure decision object: it holds the knobs (``retry_max_attempts``
/ ``rate_limit_max_attempts`` / backoff params) but performs no I/O. The caller
(an agent, or any host wrapping an LLM provider) drives the retry LOOP and asks
this policy for each decision — classification, whether to keep retrying, the
delay to sleep, and whether to rebuild the call config without the session pin.
A plugin host (MCP LLM proxy) can reuse the same decisions without importing an
agent or runtime.
"""

from __future__ import annotations

import asyncio

import httpx
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
)


class RetryPolicy:
    """Retry/backoff decisions for a single LLM call, by failure class.

    Two independent budgets are kept apart: generic transient errors and rate
    limits. A rate limit is deliberately NOT the same as a generic timeout —
    shared upstream pool overloads (DeepInfra ``engine_overloaded``) routinely
    outlast the seconds of backoff a plain timeout budget allows, so counting
    per class means one kind of failure never consumes the other's patience.
    """

    #: Exception types always classified as retryable (transient).
    _RETRYABLE_TYPES: tuple[type[Exception], ...] = (
        APITimeoutError,
        APIConnectionError,
        RateLimitError,
        InternalServerError,
        httpx.TimeoutException,
        httpx.TransportError,
        asyncio.TimeoutError,
    )

    #: Keywords that mark a message as a server/transient failure when the
    #: exception type is unknown (other providers).
    _RETRYABLE_KEYWORDS: tuple[str, ...] = (
        "rate_limit", "rate limit", "429", "too many requests",
        "server_error", "500", "502", "503", "504",
        "timeout", "timed out", "temporary", "connection", "network",
        "overloaded", "capacity",
        "expecting value", "jsondecode", "anticipate_processing_error",
    )

    #: Keywords that specifically mark a rate limit (budgeted separately).
    _RATE_LIMIT_KEYWORDS: tuple[str, ...] = (
        "rate_limit", "rate limit", "429", "too many requests",
        "engine_overloaded", "upstream_provider_shared_pool",
    )

    def __init__(
        self,
        *,
        retry_max_attempts: int = 4,
        rate_limit_max_attempts: int = 6,
        retry_base_delay_seconds: float = 1.0,
        retry_max_delay_seconds: float = 30.0,
        retry_jitter_seconds: float = 0.5,
        rate_limit_backoff_multiplier: float = 3.0,
        fallback_on_rate_limit: bool = True,
    ) -> None:
        self.retry_max_attempts: int = max(int(retry_max_attempts), 0)
        self.rate_limit_max_attempts: int = max(int(rate_limit_max_attempts), 0)
        self.retry_base_delay_seconds: float = float(retry_base_delay_seconds)
        self.retry_max_delay_seconds: float = float(retry_max_delay_seconds)
        self.retry_jitter_seconds: float = float(retry_jitter_seconds)
        self.rate_limit_backoff_multiplier: float = float(rate_limit_backoff_multiplier)
        self.fallback_on_rate_limit: bool = bool(fallback_on_rate_limit)

    # -- classification ---------------------------------------------------

    @staticmethod
    def is_rate_limit(exc: Exception) -> bool:
        """True for HTTP 429 / explicit rate-limit failures, which get a longer
        retry budget than generic transient errors (a shared upstream pool can
        stay overloaded for tens of seconds)."""
        if isinstance(exc, RateLimitError):
            return True
        if isinstance(exc, APIStatusError):
            status = getattr(exc, "status_code", None)
            if status == 429:
                return True
        error_str = str(exc).lower()
        return any(
            keyword in error_str for keyword in RetryPolicy._RATE_LIMIT_KEYWORDS
        )

    @staticmethod
    def is_retryable(exc: Exception) -> bool:
        """True for transient failures (timeouts, connection drops, rate limits,
        server errors) that are safe to retry. Classifies by exception type where
        possible, falling back to message/keyword matching for unknown providers.
        """
        for cls in RetryPolicy._RETRYABLE_TYPES:
            if isinstance(exc, cls):
                return True
        # Server-side status errors (5xx) are transient regardless of message.
        if isinstance(exc, APIStatusError):
            status = getattr(exc, "status_code", None)
            if status is not None and 500 <= status < 600:
                return True
        error_str = str(exc).lower()
        return any(keyword in error_str for keyword in RetryPolicy._RETRYABLE_KEYWORDS)

    @staticmethod
    def retry_after_seconds(exc: Exception) -> float | None:
        """Seconds to wait before retrying, from a provider Retry-After header
        (if one was sent). Returns None when absent. Only the seconds form is
        parsed; a future HTTP-date falls back to the exponential backoff."""
        response = getattr(exc, "response", None)
        if response is None:
            return None
        value = getattr(getattr(response, "headers", None), "get", None)
        if value is None:
            return None
        raw = value("retry-after")
        if not raw:
            return None
        try:
            return max(0.0, float(raw))
        except ValueError:
            return None

    # -- budgets / backoff -------------------------------------------------

    @property
    def budgets(self) -> dict[bool, int]:
        """Attempt budgets keyed by rate_limited flag (False = generic)."""
        return {False: self.retry_max_attempts, True: self.rate_limit_max_attempts}

    @property
    def worst_budget(self) -> int:
        return max(self.budgets[False], self.budgets[True])

    def delay_seconds(
        self,
        *,
        rate_limited: bool,
        retry_count: int,
        retry_after: float | None = None,
    ) -> float:
        """Backoff before the next retry.

        Exponential in the retry count for this failure class (base * 2^(n-1)),
        scaled up for rate limits, honoring a provider ``Retry-After`` header,
        and always capped at ``retry_max_delay_seconds``.
        """
        delay = self.retry_base_delay_seconds * (
            self.rate_limit_backoff_multiplier if rate_limited else 1.0
        ) * (2.0 ** (retry_count - 1))
        if retry_after is not None:
            delay = max(delay, retry_after)
        return min(delay, self.retry_max_delay_seconds)

    def should_drop_session_pin(self, *, rate_limited: bool, has_session_id: bool) -> bool:
        """Drop the session-pinned provider on a rate-limited retry so OpenRouter
        can route around the overloaded upstream pool. Generic retries keep the
        pin (prompt-cache warmth is only sacrificed for overload routing)."""
        return bool(rate_limited and self.fallback_on_rate_limit and has_session_id)

    def per_call_timeout_message(self, call_timeout_seconds: float) -> str:
        """Distinct error for a per-call deadline (``llm.call_timeout_seconds``)
        that hit on every generic attempt — the caller's run-level budget handler
        must not misreport this as ``safety.timeout_seconds`` being exhausted."""
        return (
            f"LLM call exceeded the {call_timeout_seconds}s "
            f"per-call timeout on all {self.retry_max_attempts} attempt(s)"
        )