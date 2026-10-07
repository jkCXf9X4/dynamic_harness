"""Multimodal image-input tests: tool → ToolResult → context → provider.

Verifies that a tool returning a ``ToolOutput`` with image data URIs rides the
whole chain: the registry normalizes it into ``ToolResult.images``, the agent
run loop commits a content-part tool message (text part + one image part per
image, via ``tool_message_parts``), and context accounting (token estimation,
prune markers) flattens content-part lists to their text parts instead of
stringifying them.
"""

from __future__ import annotations

import base64
from types import SimpleNamespace

from dynamic_harness.artifact.store import ArtifactStore
from dynamic_harness.core.context import AgentContext
from dynamic_harness.core.result_store import ResultStore
from dynamic_harness.core.tool_context import ToolContext
from dynamic_harness.core.tools.filesystem import read
from dynamic_harness.core.tools.registry import (
    ToolDef,
    ToolOutput,
    ToolRegistry,
)
from dynamic_harness.llm.content import (
    content_to_text,
    image_part,
    images_to_data_uri,
    text_part,
    tool_message_parts,
)

# 1x1 transparent PNG.
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQAB"
    "h6FO1AAAAABJRU5ErkJggg=="
)
URI = "data:image/png;base64,AAA"


class TestToolMessageParts:
    def test_images_become_content_parts(self) -> None:
        out = tool_message_parts("body", [URI, "data:image/jpeg;base64,BBB"])
        assert out == [
            {"type": "text", "text": "body"},
            {"type": "image_url", "image_url": {"url": URI}},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,BBB"}},
        ]

    def test_no_images_keeps_plain_string(self) -> None:
        """Text-only tool results keep the existing wire shape (str content)."""
        assert tool_message_parts("body", []) == "body"

    def test_empty_content_images_only(self) -> None:
        out = tool_message_parts("", [URI])
        assert out == [{"type": "image_url", "image_url": {"url": URI}}]


class TestContentToText:
    def test_flattens_parts_skipping_images(self) -> None:
        parts = [text_part("hi"), image_part(URI), text_part("there")]
        assert content_to_text(parts) == "hi\nthere"

    def test_plain_str_and_none(self) -> None:
        assert content_to_text("plain") == "plain"
        assert content_to_text(None) == ""

    def test_context_estimate_ignores_image_parts(self) -> None:
        """The base64 payload must not be counted: only the text part plus the
        (empty) system/assistant messages are estimated."""
        ctx = AgentContext()
        uri = images_to_data_uri(b"x" * 512, "image/png")
        ctx.commit_turn(
            {"role": "assistant", "content": "", "tool_calls": []},
            [{
                "role": "tool", "tool_call_id": "x",
                "content": tool_message_parts("photo", [uri]),
            }],
        )
        assert ctx.estimate_prompt_tokens() <= max(1, len("photo") // 4 + 8)

    def test_prune_marker_tail_uses_text_parts(self) -> None:
        ctx = AgentContext()
        uri = images_to_data_uri(b"x" * 512, "image/png")
        ctx.commit_turn(
            {"role": "assistant", "content": "", "tool_calls": []},
            [{
                "role": "tool", "tool_call_id": "x",
                "content": tool_message_parts("photo", [uri]),
            }],
        )
        marker = ctx.make_prune_marker("t0")
        assert "photo" in marker
        assert "base64" not in marker


class TestRegistryCarriesImages:
    @staticmethod
    def _registry() -> ToolRegistry:
        registry = ToolRegistry()

        async def output_with_image(*, ctx) -> ToolOutput:
            return ToolOutput(content="photo attached", images=[URI])

        async def plain(*, ctx) -> str:
            return "just text"

        schema = {"type": "object", "properties": {}}
        registry.register(
            ToolDef(name="photo_tool", description="d", input_schema=schema),
            output_with_image,
        )
        registry.register(
            ToolDef(name="plain_tool", description="d", input_schema=schema),
            plain,
        )
        return registry

    @staticmethod
    def _agent() -> SimpleNamespace:
        return SimpleNamespace(result_store=ResultStore())

    async def test_tooloutput_images_reach_toolresult(self) -> None:
        result = await self._registry().execute("photo_tool", "call-1", agent=self._agent())
        assert result.images == [URI]
        assert result.content == "photo attached"

    async def test_plain_tool_has_no_images(self) -> None:
        result = await self._registry().execute("plain_tool", "call-2", agent=self._agent())
        assert result.images == []
        assert result.content == "just text"

    async def test_tooloutput_message_shape(self) -> None:
        result = await self._registry().execute("photo_tool", "call-3", agent=self._agent())
        assert tool_message_parts(result.content, result.images) == [
            {"type": "text", "text": "photo attached"},
            {"type": "image_url", "image_url": {"url": URI}},
        ]


class TestReadToolImages:
    @staticmethod
    def _ctx(tmp_path) -> ToolContext:
        return ToolContext(SimpleNamespace(generated_root=tmp_path, skills=None))

    async def test_image_file_becomes_data_uri(self, tmp_path) -> None:
        p = tmp_path / "pixel.png"
        p.write_bytes(TINY_PNG)
        out = await read(ctx=self._ctx(tmp_path), path=str(p))
        assert isinstance(out, ToolOutput)
        assert out.images[0].startswith("data:image/png;base64,")
        assert base64.b64decode(out.images[0].split(",", 1)[1]) == TINY_PNG

    async def test_text_file_unchanged(self, tmp_path) -> None:
        p = tmp_path / "note.txt"
        p.write_text("hello")
        out = await read(ctx=self._ctx(tmp_path), path=str(p))
        assert out == "hello"

    async def test_oversized_image_refused(self, tmp_path) -> None:
        p = tmp_path / "big.png"
        p.write_bytes(b"\x89PNG" + b"0" * (5 * 1024 * 1024))
        out = await read(ctx=self._ctx(tmp_path), path=str(p))
        assert isinstance(out, str)
        assert out.startswith("Error:") and "read cap" in out


class TestArtifactStoreBinary:
    def test_bytes_round_trip(self, tmp) -> None:
        store = ArtifactStore(tmp)
        p = store.write_bytes("art1", "shot.png", TINY_PNG)
        assert p.exists()
        assert store.read_bytes("art1", "shot.png") == TINY_PNG
        assert store.read_bytes("art1", "missing.png") is None

    def test_bytes_traversal_rejected(self, tmp) -> None:
        store = ArtifactStore(tmp)
        for name in ("../escape.png", "sub/dir/x.png"):
            try:
                store.write_bytes("art1", name, TINY_PNG)
            except ValueError as e:
                assert "escapes store root" in str(e) or "Invalid artifact" in str(e)
            else:
                raise AssertionError(f"traversal not rejected for {name!r}")
