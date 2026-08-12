from __future__ import annotations

import ipaddress as _ipaddress
from typing import TYPE_CHECKING
from urllib.parse import urlparse as _urlparse

import httpx as _httpx

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

MAX_FETCH_BYTES = 200_000
MAX_REDIRECTS = 3


def _is_restricted_host(hostname: str) -> bool:
    """Reject URLs whose hostname is a literal loopback/private address."""
    try:
        addr = _ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return (
        addr.is_loopback
        or addr.is_private
        or addr.is_link_local
        or addr.is_multicast
    )


def _validate_url(url: str) -> str | None:
    """Return an error message if ``url`` is unusable, else None."""
    try:
        parsed = _urlparse(url)
    except Exception:
        return f"Error: invalid URL '{url}'"

    if parsed.scheme not in ("http", "https"):
        return f"Error: unsupported URL scheme '{parsed.scheme}'. Only http and https are allowed."

    hostname = parsed.hostname
    if not hostname:
        return f"Error: no hostname in URL '{url}'"
    if _is_restricted_host(hostname):
        return f"Error: URL resolves to a restricted address ({hostname})."
    return None


async def webfetch(*, ctx: ToolContext, url: str) -> str:
    error = _validate_url(url)
    if error:
        return error

    client = _httpx.AsyncClient(follow_redirects=False, timeout=30)
    try:
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            error = _validate_url(current)
            if error:
                return error
            try:
                async with client.stream("GET", current) as resp:
                    if resp.status_code in (301, 302, 303, 307, 308):
                        location = resp.headers.get("location")
                        if not location:
                            return f"Error: redirect to {resp.status_code} with no Location header."
                        from urllib.parse import urljoin
                        current = urljoin(str(resp.url), location)
                        continue
                    resp.raise_for_status()
                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in resp.aiter_bytes():
                        chunks.append(chunk)
                        total += len(chunk)
                        if total >= MAX_FETCH_BYTES:
                            break
                    data = b"".join(chunks)[:MAX_FETCH_BYTES].decode(errors="replace")
                    if total >= MAX_FETCH_BYTES:
                        data += (
                            f"\n\n[TRUNCATED: response exceeded {MAX_FETCH_BYTES} "
                            f"bytes; fetched first {MAX_FETCH_BYTES}]"
                        )
                    return data
            except _httpx.HTTPError as e:
                return f"Error fetching {current}: {e}"
        return f"Error: too many redirects (> {MAX_REDIRECTS})."
    finally:
        await client.aclose()
