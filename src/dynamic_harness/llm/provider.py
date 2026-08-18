from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMConfig:
    model: str = "gpt-4o"
    temperature: float = 0.0
    max_tokens: int | None = None
    provider_ignore: list[str] = field(default_factory=list)
    provider_allow_fallbacks: bool = True
    provider_force: str | None = None
    # Stable per-conversation identifier forwarded to providers that support
    # session-pinned routing/caching (OpenRouter ``session_id``). Agents reuse
    # the value across every turn so all requests of one conversation hit the
    # same provider with a warm prompt cache.
    session_id: str | None = None


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
    # Model used when a call carries no explicit LLMConfig. Providers should set
    # this at construction so callers can build per-call configs without knowing
    # the resolved model.
    default_model: str = "gpt-4o"

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

    async def aclose(self) -> None:
        """Release any underlying resources (connections, sessions, etc.)."""