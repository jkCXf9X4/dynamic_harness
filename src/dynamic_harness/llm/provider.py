from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


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


@dataclass
class ToolCallData:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolCallResponse:
    content: str | None = None
    tool_calls: list[ToolCallData] | None = None
    model: str = ""
    usage: dict | None = None


class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, system: str, user: str, config: LLMConfig | None = None) -> LLMResponse: ...

    @abstractmethod
    async def generate_with_tools(
        self, messages: list[dict], tools: list[dict], config: LLMConfig | None = None
    ) -> ToolCallResponse: ...

    @abstractmethod
    async def generate_structured(
        self, system: str, user: str, response_model: type, config: LLMConfig | None = None
    ) -> object: ...