from __future__ import annotations

import json
import re

import httpx
from openai import AsyncOpenAI

from .provider import LLMConfig, LLMProvider, LLMResponse, ToolCallData, ToolCallResponse


def _extract_json(text: str) -> object:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _extract_usage(usage: object | None) -> dict | None:
    """Surface provider prompt-cache info (``cached_tokens``) alongside raw counts.

    The OpenAI-compatible usage object exposes ``prompt_tokens_details`` on
    providers that report it (OpenAI automatic caching, OpenRouter, Ollama, ...).
    Without this the cache hit count is silently dropped and we can't see whether
    the design is actually reusing the conversation prefix across turns.
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
        timeout: httpx.Timeout | float = 120.0,
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
            # client-level timeout. Without this, the configured
            # `llm.call_timeout_seconds` cap was silently ignored and a hung
            # provider call would block far longer than intended.
            timeout=timeout,
        )
        self.default_model = model
        self._provider_ignore = provider_ignore or []
        self._provider_allow_fallbacks = provider_allow_fallbacks
        self._provider_force = provider_force
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
        resp = await self.client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            model=cfg.model,
            usage=_extract_usage(resp.usage),
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

        resp = await self.client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        msg = choice.message

        tool_calls = None
        if msg.tool_calls:
            parsed: list[ToolCallData] = []
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    try:
                        args = _extract_json(tc.function.arguments)
                    except (json.JSONDecodeError, ValueError):
                        args = {}
                parsed.append(ToolCallData(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args if isinstance(args, dict) else {},
                ))
            if parsed:
                tool_calls = parsed

        return ToolCallResponse(
            content=msg.content,
            tool_calls=tool_calls,
            model=cfg.model,
            usage=_extract_usage(resp.usage),
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