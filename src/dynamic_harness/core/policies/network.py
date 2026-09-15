"""Web-fetch safety policy as a composable policy object.

SSRF-style host validation, fetch size caps, and redirect budgets used to be
module constants + private functions inside the ``webfetch`` tool. This policy
owns those decisions so a plugin host providing a guarded ``webfetch`` MCP
wrapper — one of the advertised bridge tools — applies exactly the same
restrictions without importing the tool.

The policy is pure (URL in → verdict/message out); the tool does the I/O.
"""

from __future__ import annotations

import ipaddress as _ipaddress
import socket as _socket
from urllib.parse import urlparse


class WebFetchPolicy:
    """Decides whether a URL may be fetched and how much may be read.

    Host-agnostic: an MCP ``webfetch`` wrapper reuses the same host validation
    and budgets, so a URL the harness rejects stays rejected on the host.
    """

    MAX_FETCH_BYTES: int = 200_000
    MAX_REDIRECTS: int = 3

    def validate(self, url: str) -> str | None:
        """Return an error message if ``url`` is unusable, else None."""
        try:
            parsed = urlparse(url)
        except Exception:
            return f"Error: invalid URL '{url}'"

        if parsed.scheme not in ("http", "https"):
            return (
                f"Error: unsupported URL scheme '{parsed.scheme}'. "
                f"Only http and https are allowed."
            )

        hostname = parsed.hostname
        if not hostname:
            return f"Error: no hostname in URL '{url}'"
        if self._is_restricted_host(hostname):
            return f"Error: URL resolves to a restricted address ({hostname})."
        return None

    @staticmethod
    def _is_restricted_host(hostname: str) -> bool:
        """Reject URLs whose host resolves to a loopback/private address.

        Handles both literal IPs and hostnames. For hostnames (which a literal
        string check would miss — the DNS-rebinding bypass), we resolve the name
        and reject if ANY resolved address is private/loopback/link-local/
        multicast. An empty resolution is treated as restricted (defensive:
        we cannot prove the host is public).
        """
        # Literal IP fast path.
        try:
            addr = _ipaddress.ip_address(hostname)
        except ValueError:
            pass
        else:
            return (
                addr.is_loopback
                or addr.is_private
                or addr.is_link_local
                or addr.is_multicast
            )

        # Hostname: resolve and validate every address family we can see.
        try:
            infos = _socket.getaddrinfo(
                hostname, None, proto=_socket.IPPROTO_TCP
            )
        except _socket.gaierror:
            # Unresolvable host — cannot prove it is public; reject.
            return True

        addresses = {info[4][0] for info in infos}
        if not addresses:
            return True
        for raw in addresses:
            try:
                addr = _ipaddress.ip_address(raw)
            except ValueError:
                continue
            if (
                addr.is_loopback
                or addr.is_private
                or addr.is_link_local
                or addr.is_multicast
            ):
                return True
        return False

    def truncation_note(self, fetched_bytes: int) -> str:
        return (
            f"\n\n[TRUNCATED: response exceeded {self.MAX_FETCH_BYTES} "
            f"bytes; fetched first {self.MAX_FETCH_BYTES}]"
        )

    def too_many_redirects_message(self) -> str:
        return f"Error: too many redirects (> {self.MAX_REDIRECTS})."