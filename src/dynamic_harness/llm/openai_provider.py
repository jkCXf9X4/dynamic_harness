from __future__ import annotations

from openai import AsyncOpenAI

from .provider import LLMConfig, LLMProvider, LLMResponse


class OpenAIProvider(LLMProvider):
    def __init__(self, model: str = "gpt-4o") -> None:
        self.client = AsyncOpenAI()
        self.default_model = model

    async def generate(self, system: str, user: str, config: LLMConfig | None = None) -> LLMResponse:
        cfg = config or LLMConfig(model=self.default_model)
        resp = await self.client.chat.completions.create(
            model=cfg.model,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        choice = resp.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            model=cfg.model,
            usage={"prompt_tokens": resp.usage.prompt_tokens, "completion_tokens": resp.usage.completion_tokens} if resp.usage else None,
        )

    async def generate_structured(
        self, system: str, user: str, response_model: type, config: LLMConfig | None = None
    ) -> object:
        cfg = config or LLMConfig(model=self.default_model)
        resp = await self.client.beta.chat.completions.parse(
            model=cfg.model,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format=response_model,
        )
        return resp.choices[0].message.parsed