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


class OpenAIProvider(LLMProvider):
    def __init__(
        self,
        model: str = "gpt-4o",
        base_url: str | None = None,
        api_key: str | None = None,
        verify_ssl: bool = True,
    ) -> None:
        http_client = httpx.AsyncClient(verify=verify_ssl)
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            http_client=http_client,
        )
        self.default_model = model

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
        if cfg.max_tokens is not None:
            kwargs["max_tokens"] = cfg.max_tokens
        resp = await self.client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            model=cfg.model,
            usage={
                "prompt_tokens": resp.usage.prompt_tokens,
                "completion_tokens": resp.usage.completion_tokens,
            } if resp.usage else None,
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
            usage={
                "prompt_tokens": resp.usage.prompt_tokens,
                "completion_tokens": resp.usage.completion_tokens,
            } if resp.usage else None,
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
        if cfg.max_tokens is not None:
            kwargs["max_tokens"] = cfg.max_tokens
        try:
            resp = await self.client.beta.chat.completions.parse(**kwargs)
            return resp.choices[0].message.parsed
        except Exception:
            text = await self.generate(system, user, cfg)
            data = _extract_json(text.content)
            return response_model(**data)