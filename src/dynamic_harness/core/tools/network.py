from __future__ import annotations

import ipaddress as _ipaddress
from typing import TYPE_CHECKING
from urllib.parse import urlparse as _urlparse

import httpx as _httpx

from .registry import ToolDef

if TYPE_CHECKING:
    from ...core.agent import Agent


TOOL_WEBFETCH_DEF = ToolDef(
    name="webfetch",
    description="Fetch content from a URL",
    input_schema={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Fully qualified URL to fetch"},
        },
        "required": ["url"],
    },
)


async def webfetch(*, agent: Agent, url: str) -> str:
    try:
        parsed = _urlparse(url)
    except Exception:
        return f"Error: invalid URL '{url}'"

    if parsed.scheme not in ("http", "https"):
        return f"Error: unsupported URL scheme '{parsed.scheme}'. Only http and https are allowed."

    hostname = parsed.hostname
    if not hostname:
        return f"Error: no hostname in URL '{url}'"

    try:
        addr = _ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        if addr.is_loopback or addr.is_private or addr.is_link_local or addr.is_multicast:
            return f"Error: URL resolves to a restricted address ({hostname})."

    async with _httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=30)
        resp.raise_for_status()
        return resp.text
