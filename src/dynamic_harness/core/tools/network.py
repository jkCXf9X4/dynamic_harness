from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urljoin

import httpx as _httpx

from ..policies.network import WebFetchPolicy
from .registry import ToolDef

if TYPE_CHECKING:
    from ...core.tool_context import ToolContext

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


def _validate_url(url: str) -> str | None:
    """Back-compat: URL validation now lives in the WebFetchPolicy."""
    return WebFetchPolicy().validate(url)


async def webfetch(*, ctx: ToolContext, url: str) -> str:
    # SSRF validation + fetch/redirect budgets live in the WebFetchPolicy (the
    # same decisions an MCP webfetch wrapper would reuse).
    policy = WebFetchPolicy()
    error = policy.validate(url)
    if error:
        return error

    client = _httpx.AsyncClient(follow_redirects=False, timeout=30)
    try:
        current = url
        for _ in range(policy.MAX_REDIRECTS + 1):
            error = policy.validate(current)
            if error:
                return error
            try:
                async with client.stream("GET", current) as resp:
                    if resp.status_code in (301, 302, 303, 307, 308):
                        location = resp.headers.get("location")
                        if not location:
                            return f"Error: redirect to {resp.status_code} with no Location header."
                        current = urljoin(str(resp.url), location)
                        continue
                    resp.raise_for_status()
                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in resp.aiter_bytes():
                        chunks.append(chunk)
                        total += len(chunk)
                        if total >= policy.MAX_FETCH_BYTES:
                            break
                    data = b"".join(chunks)[:policy.MAX_FETCH_BYTES].decode(errors="replace")
                    if total >= policy.MAX_FETCH_BYTES:
                        data += policy.truncation_note(total)
                    return data
            except _httpx.HTTPError as e:
                return f"Error fetching {current}: {e}"
        return policy.too_many_redirects_message()
    finally:
        await client.aclose()