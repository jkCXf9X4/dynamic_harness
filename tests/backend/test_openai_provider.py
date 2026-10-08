"""Provider-level tests for the OpenAI provider: prompt-cache usage capture
and streamed completions.

Covers that ``prompt_tokens_details.cached_tokens`` (OpenAI automatic cache /
OpenRouter / Ollama ...) survives the round-trip and lands in the ``usage``
dict the runtime records, and that the default streamed path reassembles
content, fragmented tool-call arguments, and the trailing usage chunk — with
graceful fallback when an endpoint rejects ``stream_options`` or ``stream``
itself.
"""

from __future__ import annotations

from types import SimpleNamespace

import httpx
from openai import BadRequestError

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
    return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason="stop")])


def _chunk(content=None, tool_calls=None, finish_reason=None, usage=None) -> SimpleNamespace:
    """One streamed chunk (``ChatCompletionChunk`` shape)."""
    delta = None
    if content is not None or tool_calls:
        delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(delta=delta, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice], usage=usage)


class _FakeStream:
    """Minimal async iterator over pre-built chunks (the provider does
    ``async for chunk in stream``)."""

    def __init__(self, chunks: list) -> None:
        self._chunks = list(chunks)
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._chunks:
            raise StopAsyncIteration
        return self._chunks.pop(0)

    async def close(self) -> None:
        self.closed = True


def _tool_chunk(index: int, id: str | None = None, name: str | None = None,
                arguments: str | None = None) -> SimpleNamespace:
    fn = SimpleNamespace(name=name, arguments=arguments) if (name or arguments) else None
    return SimpleNamespace(index=index, id=id, function=fn)


def streamed_create(response: SimpleNamespace):
    """Fake ``chat.completions.create`` that speaks the streaming protocol.

    ``stream=False`` (or absent) returns the plain response object; ``stream``
    returns an async stream with one content/tool-call chunk followed by the
    trailing usage chunk — the same shape the OpenAI/vLLM endpoints emit.
    """

    async def _create(**kwargs):
        _create.last_call = kwargs
        if not kwargs.get("stream"):
            return response
        msg = response.choices[0].message
        chunks: list = []
        if msg.content or msg.tool_calls:
            chunks.append(_chunk(
                content=msg.content,
                tool_calls=([_tool_chunk(0, id=f"tc-{i}", name=tc.function.name,
                                         arguments=tc.function.arguments)
                             for i, tc in enumerate(msg.tool_calls)] if msg.tool_calls else None),
                finish_reason="stop",
            ))
        if response.usage is not None and (kwargs.get("stream_options") or {}).get("include_usage"):
            chunks.append(_chunk(usage=response.usage))
        return _FakeStream(chunks)

    return _create


def _make_provider(response: SimpleNamespace, base_url: str = "http://localhost",
                   **provider_kwargs) -> OpenAIProvider:
    provider = OpenAIProvider(model="gpt-4o", base_url=base_url, api_key="test",
                              **provider_kwargs)
    fake_client = SimpleNamespace()
    fake_client.chat = SimpleNamespace(completions=SimpleNamespace(create=streamed_create(response)))
    provider.client = fake_client  # type: ignore[assignment]
    return provider


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
            return await streamed_create(resp)(**kwargs)
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
            return await streamed_create(resp)(**kwargs)
        provider.client.chat.completions.create = recorder

        await provider.generate_with_tools(
            messages=[], tools=[], config=LLMConfig(session_id="conv-42")
        )
        call = self._last_call(provider)
        assert call.get("extra_body") is None or "session_id" not in call.get("extra_body")

    async def test_no_session_id_sends_no_extra_body(self) -> None:
        resp = _choice(SimpleNamespace(content="ok", tool_calls=[]))
        resp.usage = _usage(prompt=1, completion=1)
        provider = _make_provider(resp)
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


class TestStreaming:
    async def test_streams_by_default_and_requests_usage(self) -> None:
        resp = _choice(SimpleNamespace(content="hello", tool_calls=[]))
        resp.usage = _usage(prompt=10, completion=1)
        provider = _make_provider(resp)
        out = await provider.generate(system="s", user="u")
        call = provider.client.chat.completions.create.last_call
        assert call["stream"] is True
        assert call["stream_options"] == {"include_usage": True}
        assert out.content == "hello"
        assert out.usage == {"prompt_tokens": 10, "completion_tokens": 1}

    async def test_reassembles_content_and_fragmented_tool_calls(self) -> None:
        """Content and tool-call arguments arrive in fragments across chunks,
        keyed by index (two concurrent tool calls interleaved)."""
        async def create(**kwargs):
            create.last_call = kwargs
            return _FakeStream([
                _chunk(content="Let me "),
                _chunk(content="check."),
                _chunk(tool_calls=[_tool_chunk(0, id="a1", name="read", arguments='{"pa')]),
                _chunk(tool_calls=[_tool_chunk(1, id="b2", name="grep", arguments='{"pa')]),
                _chunk(tool_calls=[_tool_chunk(0, arguments='th": "/tmp/x"}')]),
                _chunk(tool_calls=[_tool_chunk(1, arguments='th": "/tmp/y"}')]),
                _chunk(usage=_usage(prompt=42, completion=7)),
            ])
        provider = _make_provider(_choice(SimpleNamespace(content=None, tool_calls=[])))
        provider.client.chat.completions.create = create  # type: ignore[assignment]

        out = await provider.generate_with_tools(messages=[], tools=[])
        assert out.content == "Let me check."
        assert [tc.id for tc in out.tool_calls] == ["a1", "b2"]
        assert [tc.name for tc in out.tool_calls] == ["read", "grep"]
        assert out.tool_calls[0].arguments == {"path": "/tmp/x"}
        assert out.tool_calls[1].arguments == {"path": "/tmp/y"}
        assert out.usage == {"prompt_tokens": 42, "completion_tokens": 7}

    async def test_truncated_tool_arguments_degrade_to_empty(self) -> None:
        """A call cut off mid-JSON by max_tokens must not crash the provider:
        the argument set degrades to {} (finish_reason='length')."""
        async def create(**kwargs):
            return _FakeStream([
                _chunk(tool_calls=[_tool_chunk(0, id="a1", name="write",
                                               arguments='{"content": "unclosed')]),
                _chunk(finish_reason="length"),
            ])
        provider = _make_provider(_choice(SimpleNamespace(content=None, tool_calls=[])))
        provider.client.chat.completions.create = create  # type: ignore[assignment]
        out = await provider.generate_with_tools(messages=[], tools=[])
        assert out.tool_calls[0].name == "write"
        assert out.tool_calls[0].arguments == {}

    async def test_stream_options_rejection_drops_usage_but_keeps_stream(self) -> None:
        """Older vLLM / stripping proxies 400 on stream_options: one retry
        without it — streaming is kept, usage is dropped (None)."""
        request = httpx.Request("POST", "http://endpoint.invalid/v1/chat/completions")
        resp = _choice(SimpleNamespace(content="ok", tool_calls=[]))
        resp.usage = _usage(prompt=1, completion=1)
        provider = _make_provider(resp)

        calls: list[dict] = []

        async def create(**kwargs):
            calls.append(kwargs)
            if kwargs.get("stream_options"):
                raise BadRequestError(
                    message="BadRequest: stream_options is not supported",
                    response=httpx.Response(400, request=request),
                    body=None,
                )
            return _FakeStream([_chunk(content="ok")])

        provider.client.chat.completions.create = create  # type: ignore[assignment]
        out = await provider.generate(system="s", user="u")
        assert len(calls) == 2
        assert calls[0]["stream_options"] == {"include_usage": True}
        assert "stream_options" not in calls[1]
        assert calls[1]["stream"] is True
        assert out.content == "ok"
        assert out.usage is None

    async def test_stream_rejection_falls_back_to_non_streamed(self) -> None:
        """An endpoint that rejects streaming altogether gets the legacy
        single-response call for the provider's lifetime."""
        request = httpx.Request("POST", "http://endpoint.invalid/v1/chat/completions")
        resp = _choice(SimpleNamespace(content="ok", tool_calls=[]))
        resp.usage = _usage(prompt=1, completion=1)
        provider = _make_provider(resp)

        calls: list[dict] = []

        async def create(**kwargs):
            calls.append(kwargs)
            if kwargs.get("stream"):
                raise BadRequestError(
                    message="BadRequest: streaming is not supported",
                    response=httpx.Response(400, request=request),
                    body=None,
                )
            return resp

        provider.client.chat.completions.create = create  # type: ignore[assignment]
        out = await provider.generate(system="s", user="u")
        assert provider._stream is False
        assert len(calls) == 2
        assert calls[0].get("stream") is True
        assert "stream" not in calls[1]
        assert out.content == "ok"
        assert out.usage == {"prompt_tokens": 1, "completion_tokens": 1}

    async def test_stream_disabled_uses_non_streamed(self) -> None:
        resp = _choice(SimpleNamespace(content="ok", tool_calls=[]))
        resp.usage = _usage(prompt=1, completion=1)
        provider = _make_provider(resp, stream=False)
        out = await provider.generate(system="s", user="u")
        call = provider.client.chat.completions.create.last_call
        assert "stream" not in call
        assert out.content == "ok"
        assert out.usage == {"prompt_tokens": 1, "completion_tokens": 1}
