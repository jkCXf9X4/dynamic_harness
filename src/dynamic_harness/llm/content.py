"""Multimodal message-content helpers (OpenAI content-part wire shape).

Image-capable models accept image input as content-part arrays. Tools produce
images as base64 data URIs (see ``ToolOutput``); the agent run loop attaches
them to the committed tool message via ``tool_message_parts``. Text-only
conversations never change shape: with no images the wire content stays a
plain string, so text-only tool results and prune/compress accounting are
unaffected.
"""

from __future__ import annotations

import base64
from typing import Any


def text_part(text: str) -> dict[str, Any]:
    return {"type": "text", "text": text}


def image_part(url: str) -> dict[str, Any]:
    return {"type": "image_url", "image_url": {"url": url}}


def images_to_data_uri(data: bytes, mime: str) -> str:
    """Encode raw image bytes as a base64 data URI."""
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def tool_message_parts(content: str, images: list[str]) -> str | list[dict[str, Any]]:
    """Wire shape for a tool-result message carrying images: a text part
    followed by one image part per image (OpenAI content-part shape).

    Plain string content when there are no images — the common path, so
    text-only tool results keep their existing shape.
    """
    if not images:
        return content
    parts: list[dict[str, Any]] = []
    if content:
        parts.append(text_part(content))
    parts.extend(image_part(uri) for uri in images)
    return parts


def content_to_text(content: str | list | None) -> str:
    """Flatten message content (plain string or content-part list) to text.

    Image parts contribute nothing — used by token estimation, truncation and
    prune markers, which reason about text only.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return "\n".join(
        str(part.get("text") or "")
        for part in content
        if isinstance(part, dict) and part.get("type") == "text"
    )
