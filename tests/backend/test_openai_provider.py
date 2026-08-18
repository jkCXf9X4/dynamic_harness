"""Provider-level tests for surfacing prompt-cache info from the API.

Verifies that ``prompt_tokens_details.cached_tokens`` (OpenAI automatic cache /
OpenRouter / Ollama ...) survives the round-trip through the OpenAI provider and
lands in the ``usage`` dict that the runtime records. Without this the cache hit
count is silently dropped and we cannot measure whether the conversation prefix
is actually being reused across turns.
"""

from __future__ import annotations

from types import SimpleNamespace

from dynamic_harness.llm.openai_provider import OpenAIProvider
from dynamic_harness.llm.provider import LLMConfig


def _usage(prompt: int, completion: int, cached: int | None = None) -> SimpleNamespace:
    details = SimpleNamespace(cached_tokens=cached) if cached is not None else None
    return SimpleNamespace(
        prompt_tokens=prompt,
        completion_tokens=completion,
        prompt_tokens_details=details,
    )


def _choice(message: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _make_provider(response: SimpleNamespace, base_url: str = "http://localhost") -> OpenAIProvider:
    provider = OpenAIProvider(model="gpt-4o", base_url=base_url, api_key="test")
    fake_client = SimpleNamespace()
    fake_client.chat = SimpleNamespace(
        completions=SimpleNamespace(create=response_fn(response))
    )
    provider.client = fake_client  # type: ignore[assignment]
    return provider


def response_fn(response: SimpleNamespace):
    async def _create(**kwargs):
        return response
    return _create


class TestNullResponse:
    async def test_null_usage_is_none(self) -> None:
        resp = _choice(SimpleNamespace(content="done", tool_calls=[]))
        resp.usage = None
        provider = _make_provider(resp)
        out = await provider.generate(system="s", user="u")
        assert out.usage is None


OPENROUTER = "https://openrouter.ai/api/v1"


class TestSessionIdForwarding:
    @staticmethod
    def _last_call(provider: OpenAIProvider) -> dict:
        return provider.client.chat.completions.create.last_call

    async def test_openrouter_forwards_session_id(self) -> None:
        """A session_id must reach the wire as an OpenRouter body field."""
        resp = _choice(SimpleNamespace(content="ok", tool_calls=[]))
        resp.usage = _usage(prompt=1, completion=1)
        provider = _make_provider(resp, base_url=OPENROUTER)

        async def recorder(**kwargs):
            recorder.last_call = kwargs
            return resp
        provider.client.chat.completions.create = recorder

        await provider.generate_with_tools(
            messages=[], tools=[], config=LLMConfig(session_id="conv-42")
        )
        assert self._last_call(provider)["extra_body"]["session_id"] == "conv-42"

    async def test_non_openrouter_omits_session_id(self) -> None:
        """OpenAI's native API rejects unknown body keys, so session_id must NOT
        be forwarded anywhere but OpenRouter."""
        resp = _choice(SimpleNamespace(content="ok", tool_calls=[]))
        resp.usage = _usage(prompt=1, completion=1)
        provider = _make_provider(resp, base_url="https://api.openai.com/v1")

        async def recorder(**kwargs):
            recorder.last_call = kwargs
            return resp
        provider.client.chat.completions.create = recorder

        await provider.generate_with_tools(
            messages=[], tools=[], config=LLMConfig(session_id="conv-42")
        )
        call = self._last_call(provider)
        assert call.get("extra_body") is None or "session_id" not in call.get("extra_body")

    async def test_no_session_id_sends_no_extra_body(self) -> None:
        resp = _choice(SimpleNamespace(content="ok", tool_calls=[]))
        resp.usage = _usage(prompt=1, completion=1)
        provider = _make_provider(resp, base_url=OPENROUTER)

        async def recorder(**kwargs):
            recorder.last_call = kwargs
            return resp
        provider.client.chat.completions.create = recorder

        await provider.generate(system="s", user="u", config=LLMConfig())
        assert self._last_call(provider).get("extra_body") is None


class TestCachedTokensCapture:
    async def test_generate_with_tools_captures_cached_tokens(self) -> None:
        resp = _choice(SimpleNamespace(content=None, tool_calls=[]))
        resp.usage = _usage(prompt=5000, completion=10, cached=3328)
        provider = _make_provider(resp)
        out = await provider.generate_with_tools(messages=[], tools=[])
        assert out.usage is not None
        assert out.usage["prompt_tokens"] == 5000
        assert out.usage["completion_tokens"] == 10
        assert out.usage["cached_tokens"] == 3328

    async def test_generate_captures_cached_tokens(self) -> None:
        resp = _choice(SimpleNamespace(content="ok", tool_calls=[]))
        resp.usage = _usage(prompt=800, completion=5, cached=400)
        provider = _make_provider(resp)
        out = await provider.generate(system="s", user="u")
        assert out.usage is not None
        assert out.usage["cached_tokens"] == 400

    async def test_no_details_omits_cached_key(self) -> None:
        # Providers that don't report cache (or report None) must not fabricate one.
        resp = _choice(SimpleNamespace(content=None, tool_calls=[]))
        resp.usage = _usage(prompt=100, completion=5)
        provider = _make_provider(resp)
        out = await provider.generate_with_tools(messages=[], tools=[])
        assert out.usage is not None
        assert "cached_tokens" not in out.usage

    async def test_null_usage_is_none(self) -> None:
        resp = _choice(SimpleNamespace(content="done", tool_calls=[]))
        resp.usage = None
        provider = _make_provider(resp)
        out = await provider.generate(system="s", user="u")
        assert out.usage is None