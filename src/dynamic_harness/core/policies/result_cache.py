"""Result-caching and output-tuning as a composable policy object.

This is the policy half of the ``result_read`` mechanism: a tool may declare
its output cacheable-behind-an-opaque-handle, and every cacheable output is
snapshotted before truncation so a read-only pager can page it later without
re-executing the producing tool. The registry executes tools; this policy
decides what is cacheable and how a (possibly truncated) view is rendered.

The pure helpers are host-agnostic: the same decisions and footer strings can
be repurposed by an MCP result-cache server wrapping third-party tools.
"""

from __future__ import annotations

from ..result_store import ResultStore


class ResultCachePolicy:
    """Cacheability decisions and token-based rendering for tool output.

    ``DEFAULT_NON_CACHEABLE`` mirrors the registry's mutator set: tools whose
    output must never be resurrected by ``result_read`` because they mutate
    state, move execution, drive control flow, or are themselves views over
    other results.
    """

    DEFAULT_NON_CACHEABLE: frozenset[str] = frozenset({
        "write", "edit", "delegate", "report", "escalate", "fail", "kill", "ask",
        "archive", "prune", "restore", "compress", "converse", "resume",
        "result_read",
    })

    def __init__(
        self,
        non_cacheable: frozenset[str] | set[str] | None = None,
    ) -> None:
        self._non_cacheable: frozenset[str] = frozenset(
            non_cacheable if non_cacheable is not None else self.DEFAULT_NON_CACHEABLE
        )

    @property
    def non_cacheable(self) -> frozenset[str]:
        return self._non_cacheable

    def is_cacheable(self, name: str) -> bool:
        return name not in self._non_cacheable

    def snapshot(self, store: ResultStore, name: str, content: str) -> str | None:
        """Store a full tool output behind a handle; return the handle or None
        for tools whose output is never cached."""
        if not self.is_cacheable(name):
            return None
        return store.store(content)

    def render(
        self,
        content: str,
        *,
        token_limit: int,
        token_offset: int,
        name: str,
        result_id: str | None,
    ) -> str:
        """Slice ``content`` by token window and append the paging footer.

        ``1 token ≈ 4 chars``. When truncated and a handle exists, the footer
        advertises ``result_read`` (page without re-running); otherwise it
        tells the model to re-run the tool / raise the limit.
        """
        char_limit = max(1, token_limit * 4)
        char_offset = max(0, token_offset * 4)
        total_chars = len(content)
        if char_offset >= total_chars:
            hint = (
                f" (result_id={result_id}; page with result_read "
                "using a smaller token_offset)" if result_id else ""
            )
            return f"(offset beyond content length){hint}"
        content = content[char_offset:]
        if len(content) > char_limit:
            content = content[:char_limit]
            if result_id:
                content += (
                    f"\n... ({token_limit} tokens shown, {total_chars // 4} total. "
                    f"Page without re-running: result_read(result_id=\"{result_id}\", "
                    f"token_offset={token_offset + token_limit}). "
                    f"Call {name} again for a fresh result. (more)"
                )
            elif name == "bash":
                # Bash output (bash is non-cacheable only in the pathological
                # case above; normally it IS cached) — keep a safe fallback.
                content += (
                    f"\n... ({token_limit} tokens shown, {total_chars // 4} total. "
                    "To see more, re-run THIS command with a larger "
                    f"token_limit (e.g. {max(token_limit * 2, 200)})."
                )
            else:
                content += (
                    f"\n... ({token_limit} tokens shown, {total_chars // 4} total. "
                    f"Use token_limit={max(token_limit * 2, 200)} "
                    f"or token_offset={token_offset + token_limit} to see more)"
                )
        return content