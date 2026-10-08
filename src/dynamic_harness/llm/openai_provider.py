from __future__ import annotations

import json
import re
from typing import Any

import httpx
from openai import AsyncOpenAI, BadRequestError

from .provider import LLMConfig, LLMProvider, LLMResponse, ToolCallData, ToolCallResponse


def _extract_json(text: str) -> object:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _parse_arguments(raw: str) -> dict[str, Any]:
    """Parse a tool-call argument string.

    Malformed or truncated payloads (a streamed call cut off mid-JSON by
    ``max_tokens``) degrade to ``{}`` — the agent sees an empty argument set
    instead of a provider-level crash."""
    try:
        args = json.loads(raw)
    except json.JSONDecodeError:
        try:
            args = _extract_json(raw)
        except (json.JSONDecodeError, ValueError):
            return {}
    return args if isinstance(args, dict) else {}


def _extract_usage(usage: object | None) -> dict | None:
    """Surface provider cost + prompt-cache info alongside raw token counts.

    The OpenAI-compatible usage object exposes ``prompt_tokens_details`` on
    providers that report it (OpenAI automatic caching, OpenRouter, Ollama, ...)
    and, on OpenRouter, a ``cost`` field — the actual USD/credit cost of the
    request as billed (OpenRouter routes across providers by best price, so a
    preset per-1M-token price would be wrong). Without these the cache hit count
    and the real cost are silently dropped.
    """
    if usage is None:
        return None
    out: dict = {
        "prompt_tokens": getattr(usage, "prompt_tokens", 0),
        "completion_tokens": getattr(usage, "completion_tokens", 0),
    }
    details = getattr(usage, "prompt_tokens_details", None)
    if details is not None:
        cached = getattr(details, "cached_tokens", None)
        if cached is not None:
            out["cached_tokens"] = int(cached)
    cost = getattr(usage, "cost", None)
    if cost is not None:
        out["cost"] = float(cost)
    return out


class OpenAIProvider(LLMProvider):
    def __init__(
        self,
        model: str = "gpt-4o",
        base_url: str | None = None,
        api_key: str | None = None,
        verify_ssl: bool = True,
        provider_ignore: list[str] | None = None,
        provider_allow_fallbacks: bool = True,
        provider_force: str | None = None,
        timeout: httpx.Timeout | float = 500.0,
        max_retries: int = 0,
        stream: bool = True,
    ) -> None:
        http_client = httpx.AsyncClient(verify=verify_ssl, timeout=timeout)
        self._http_client = http_client
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            http_client=http_client,
            # Pass the timeout to the SDK as well: the openai client bakes its
            # OWN default timeout (600s read/write/pool) into every request
            # (`_base_client.build_request`), which overrides the httpx
            # client-level timeout. Without this the configured
            # `llm.call_timeout_seconds` cap was silently ignored and a hung
            # provider call would block far longer than intended.
            timeout=timeout,
            # The SDK transparently retries on timeout/connection errors up to
            # `max_retries` (default 2) times, silently multiplying the effective
            # wait by up to ~3x per call. The agent already owns retry/backoff
            # (`Agent._llm_call_with_retry`); letting both layers retry compounds
            # the stall into ~12x the configured timeout. Default 0 so the
            # configured `call_timeout_seconds` is honored on the first attempt.
            max_retries=max_retries,
        )
        self.default_model = model
        self._provider_ignore = provider_ignore or []
        self._provider_allow_fallbacks = provider_allow_fallbacks
        self._provider_force = provider_force
        # Streamed completions keep the wire active while the model generates,
        # so a gateway with a total-request-time cap (the SAGA vLLM gateway
        # 504s ``gateway_timeout`` after 300s) does not kill a long generation
        # the way it kills a silent non-streamed request. ``stream=False``
        # restores the legacy single-response call for endpoints that cannot
        # forward chunked responses.
        self._stream = bool(stream)
        # Endpoints that reject ``stream_options`` (older vLLM / stripping
        # proxies) get one automatic retry without it: streaming is kept,
        # usage reporting is dropped (``usage`` -> None).
        self._stream_include_usage = True
        # ``session_id`` is an OpenRouter-specific field; OpenAI's native API
        # rejects unknown body keys, so only forward it to OpenRouter.
        self._is_openrouter = base_url is not None and "openrouter" in base_url.lower()

    def _build_extra_body(self, cfg: LLMConfig) -> dict | None:
        body: dict = {}
        force = cfg.provider_force or self._provider_force
        if force:
            body["provider"] = {
                "order": [force],
                "allow_fallbacks": False,
                "ignore": cfg.provider_ignore or self._provider_ignore,
            }
        else:
            ignore = cfg.provider_ignore or self._provider_ignore
            if ignore:
                body["provider"] = {
                    "ignore": ignore,
                    "allow_fallbacks": cfg.provider_allow_fallbacks
                    if cfg.provider_ignore
                    else self._provider_allow_fallbacks,
                }
        # OpenRouter: a per-conversation session pins every turn to one provider
        # so its prompt cache stays warm across the whole agent run.
        if self._is_openrouter and cfg.session_id:
            body["session_id"] = cfg.session_id
        return body or None

    async def generate(self, system: str, user: str, config: LLMConfig | None = None) -> LLMResponse:
        cfg = config or LLMConfig(model=self.default_model)
        kwargs: dict = dict(
            model=cfg.model,
            temperature=cfg.temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        extra = self._build_extra_body(cfg)
        if extra:
            kwargs["extra_body"] = extra
        if cfg.max_tokens is not None:
            kwargs["max_tokens"] = cfg.max_tokens
        content, _, usage, _ = await self._create_chat(**kwargs)
        return LLMResponse(
            content=content,
            model=cfg.model,
            usage=usage,
        )

    async def generate_with_tools(
        self, messages: list[dict], tools: list[dict], config: LLMConfig | None = None
    ) -> ToolCallResponse:
        cfg = config or LLMConfig(model=self.default_model)
        kwargs: dict = dict(
            model=cfg.model,
            temperature=cfg.temperature,
            messages=messages,
        )
        extra = self._build_extra_body(cfg)
        if extra:
            kwargs["extra_body"] = extra
        if cfg.max_tokens is not None:
            kwargs["max_tokens"] = cfg.max_tokens
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        content, tool_calls, usage, _ = await self._create_chat(**kwargs)
        return ToolCallResponse(
            content=content or None,
            tool_calls=tool_calls,
            model=cfg.model,
            usage=usage,
        )

    # -- chat completion: streamed by default -------------------------------

    async def _create_chat(
        self, **kwargs
    ) -> tuple[str, list[ToolCallData] | None, dict | None, str | None]:
        """Run one chat completion, streamed by default.

        Returns ``(content, tool_calls, usage, finish_reason)``. Streaming
        keeps the wire active while the model generates, so a gateway or
        load balancer with a total-request-time cap (the SAGA vLLM gateway
        returns a 504 ``gateway_timeout`` after 300s) does not kill a long
        generation the way it kills a silent non-streamed request.
        """
        if not self._stream:
            return await self._create_non_streamed(**kwargs)
        try:
            return await self._create_streamed(**kwargs)
        except BadRequestError as e:
            detail = str(e).lower()
            if "stream_options" in detail and self._stream_include_usage:
                # Endpoint rejects stream_options (older vLLM / a proxy that
                # strips unknown body keys): keep streaming, drop the usage
                # request (``usage`` -> None). One-shot per provider instance.
                self._stream_include_usage = False
                return await self._create_streamed(**kwargs)
            if "stream" in detail:
                # Endpoint rejects streaming altogether: fall back to the
                # single-response call for this provider instance's lifetime.
                self._stream = False
                return await self._create_non_streamed(**kwargs)
            raise

    async def _create_streamed(
        self, **kwargs
    ) -> tuple[str, list[ToolCallData] | None, dict | None, str | None]:
        """Stream a chat completion, reassembling content, tool calls
        (arguments arrive in fragments across chunks, keyed by index), and the
        trailing usage chunk (``stream_options.include_usage``)."""
        request = dict(kwargs)
        request["stream"] = True
        if self._stream_include_usage:
            request["stream_options"] = {"include_usage": True}
        stream = await self.client.chat.completions.create(**request)
        content_parts: list[str] = []
        tool_acc: dict[int, dict] = {}
        usage: object | None = None
        finish_reason: str | None = None
        try:
            async for chunk in stream:
                if getattr(chunk, "usage", None) is not None:
                    usage = chunk.usage
                for choice in chunk.choices:
                    if choice.finish_reason:
                        finish_reason = choice.finish_reason
                    delta = choice.delta
                    if delta is None:
                        continue
                    if delta.content:
                        content_parts.append(delta.content)
                    for tc in delta.tool_calls or []:
                        idx = tc.index if tc.index is not None else 0
                        slot = tool_acc.setdefault(
                            idx, {"id": None, "name": None, "arguments": ""}
                        )
                        if tc.id:
                            slot["id"] = tc.id
                        fn = tc.function
                        if fn is not None:
                            if fn.name:
                                slot["name"] = fn.name
                            if fn.arguments:
                                slot["arguments"] += fn.arguments
        except BaseException:
            # Cancellation (the agent's per-call deadline) tears the stream
            # down instead of leaking the connection.
            await stream.close()
            raise
        tool_calls: list[ToolCallData] = []
        for idx in sorted(tool_acc):
            slot = tool_acc[idx]
            tool_calls.append(ToolCallData(
                id=slot["id"] or f"stream-tool-{idx}",
                name=slot["name"] or "",
                arguments=_parse_arguments(slot["arguments"]),
            ))
        return (
            "".join(content_parts),
            tool_calls or None,
            _extract_usage(usage),
            finish_reason,
        )

    async def _create_non_streamed(
        self, **kwargs
    ) -> tuple[str, list[ToolCallData] | None, dict | None, str | None]:
        """The legacy single-response call (``stream=False`` providers and the
        streaming fallbacks)."""
        resp = await self.client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        msg = choice.message
        tool_calls = None
        if msg.tool_calls:
            tool_calls = [
                ToolCallData(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=_parse_arguments(tc.function.arguments),
                )
                for tc in msg.tool_calls
            ]
        return (
            msg.content or "",
            tool_calls or None,
            _extract_usage(resp.usage),
            choice.finish_reason,
        )

    async def generate_structured(
        self, system: str, user: str, response_model: type, config: LLMConfig | None = None
    ) -> object:
        cfg = config or LLMConfig(model=self.default_model)
        kwargs: dict = dict(
            model=cfg.model,
            temperature=cfg.temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format=response_model,
        )
        extra = self._build_extra_body(cfg)
        if extra:
            kwargs["extra_body"] = extra
        if cfg.max_tokens is not None:
            kwargs["max_tokens"] = cfg.max_tokens
        try:
            resp = await self.client.beta.chat.completions.parse(**kwargs)
            return resp.choices[0].message.parsed
        except Exception:
            text = await self.generate(system, user, cfg)
            data = _extract_json(text.content)
            if not isinstance(data, dict):
                raise TypeError(
                    f"generate_structured fallback expected a JSON object, got {type(data).__name__}"
                )
            return response_model(**data)

    async def aclose(self) -> None:
        await self._http_client.aclose()