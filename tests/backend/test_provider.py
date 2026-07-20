from __future__ import annotations

import pytest

from dynamic_harness.llm.provider import (
    LLMConfig,
    LLMProvider,
    LLMResponse,
    ToolCallData,
    ToolCallResponse,
)


class TestLLMConfig:
    def test_defaults(self) -> None:
        cfg = LLMConfig()
        assert cfg.model == "gpt-4o"
        assert cfg.temperature == 0.0
        assert cfg.max_tokens is None
        assert cfg.provider_ignore == []
        assert cfg.provider_allow_fallbacks is True

    def test_custom_values(self) -> None:
        cfg = LLMConfig(
            model="custom-model",
            temperature=0.7,
            max_tokens=4096,
            provider_ignore=["openai"],
            provider_allow_fallbacks=False,
        )
        assert cfg.model == "custom-model"
        assert cfg.temperature == 0.7
        assert cfg.max_tokens == 4096
        assert cfg.provider_ignore == ["openai"]
        assert cfg.provider_allow_fallbacks is False


class TestLLMResponse:
    def test_basic_creation(self) -> None:
        resp = LLMResponse(content="Hello", model="gpt-4o")
        assert resp.content == "Hello"
        assert resp.model == "gpt-4o"
        assert resp.usage is None

    def test_with_usage(self) -> None:
        resp = LLMResponse(
            content="Hi",
            model="gpt-4o",
            usage={"total_tokens": 42, "prompt_tokens": 10, "completion_tokens": 32},
        )
        assert resp.usage["total_tokens"] == 42


class TestToolCallData:
    def test_creation(self) -> None:
        tc = ToolCallData(
            id="call_1",
            name="read",
            arguments={"path": "/workspace/test.py"},
        )
        assert tc.id == "call_1"
        assert tc.name == "read"
        assert tc.arguments["path"] == "/workspace/test.py"


class TestToolCallResponse:
    def test_content_only(self) -> None:
        resp = ToolCallResponse(content="Done", model="gpt-4o")
        assert resp.content == "Done"
        assert resp.tool_calls is None

    def test_with_tool_calls(self) -> None:
        tc = ToolCallData(id="call_1", name="write", arguments={"path": "/f", "content": "c"})
        resp = ToolCallResponse(
            tool_calls=[tc],
            model="gpt-4o",
        )
        assert resp.content is None
        assert resp.tool_calls is not None
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].name == "write"

    def test_content_and_tool_calls(self) -> None:
        tc = ToolCallData(id="call_1", name="read", arguments={"path": "/f"})
        resp = ToolCallResponse(
            content="Let me check that file.",
            tool_calls=[tc],
            model="gpt-4o",
        )
        assert resp.content == "Let me check that file."
        assert len(resp.tool_calls) == 1

    def test_model_default_empty_string(self) -> None:
        resp = ToolCallResponse()
        assert resp.model == ""


class TestLLMProviderABC:
    def test_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            LLMProvider()  # type: ignore[abstract]

    def test_concrete_subclass_must_implement_all(self) -> None:
        class PartialProvider(LLMProvider):
            async def generate(self, system, user, config=None):
                return LLMResponse(content="ok", model="test")

            async def generate_with_tools(self, messages, tools, config=None):
                return ToolCallResponse(content="ok", model="test")

        with pytest.raises(TypeError):
            PartialProvider()

    def test_fully_implemented_subclass_works(self) -> None:
        class FullProvider(LLMProvider):
            async def generate(self, system, user, config=None):
                return LLMResponse(content="ok", model="test")

            async def generate_with_tools(self, messages, tools, config=None):
                return ToolCallResponse(content="ok", model="test")

            async def generate_structured(self, system, user, response_model, config=None):
                return None

        provider = FullProvider()
        assert isinstance(provider, LLMProvider)