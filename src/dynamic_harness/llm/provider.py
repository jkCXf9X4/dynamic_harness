from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMConfig:
    model: str = "gpt-4o"
    temperature: float = 0.0
    max_tokens: int = 4096


@dataclass
class LLMResponse:
    content: str
    model: str
    usage: dict | None = None


class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, system: str, user: str, config: LLMConfig | None = None) -> LLMResponse: ...

    @abstractmethod
    async def generate_structured(
        self, system: str, user: str, response_model: type, config: LLMConfig | None = None
    ) -> object: ...