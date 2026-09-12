"""Context-management decisions as a composable policy object.

``AgentContext`` kept two implicit heuristics reason about the context: the
token-proxy (``chars / 3.8`` vs ``words * 1.5``) and the compress retry count.
The same proxy is needed by anyone rendering tool pages or estimating context
cost. This policy owns those numbers so a plugin host reusing the context or
paging decisions applies identical estimates.
"""

from __future__ import annotations


class ContextMetricPolicy:
    """Token-estimation + context-reduction decisions for conversation state.

    Host-agnostic: an MCP context/artifact renderer reuses the same estimate so
    model-facing "token" numbers agree across the harness and the host.
    """

    #: Token proxies (provider-agnostic): ~3.8 chars / ~1.5 words per token.
    #: The ResultCachePolicy pager uses a coarser ``1 token ≈ 4 chars``; both
    #: are intentionally cheap, tunable heuristics rather than a real tokenizer.
    CHARS_PER_TOKEN: float = 3.8
    WORDS_PER_TOKEN: float = 1.5
    #: Max LLM attempts when compressing a context.
    COMPRESS_RETRY_ATTEMPTS: int = 2

    #: The prompt sent to the LLM when a context is compressed. Lives here so
    #: the wording belongs to the context-metrics policy (host-agnostic,
    #: reusable by any compression caller) instead of being inlined in a tool
    #: façade or the agent loop.
    COMPRESS_PROMPT: str = "\n".join([
        "You are a context compression engine. Condense the following agent",
        "conversation into a single concise paragraph. Preserve:",
        "- The original task and goals",
        "- Key findings, decisions, and code changes",
        "- Open questions and unresolved issues",
        "- Current state and next steps",
        "Output ONLY the summary paragraph, no preamble.",
    ])

    @staticmethod
    def estimate_tokens(text: str | None) -> int:
        """Ballpark token count for a string, provider-agnostic.

        Returns 0 for empty/None input. Blends two cheap proxies and takes the
        higher so code (fewer spaces, denser punctuation) and prose (longer
        words) both land in the right ballpark without pulling in a tokenizer
        dependency.
        """
        if not text:
            return 0
        chars = float(len(text))
        words = float(len(text.split()))
        est = max(chars / ContextMetricPolicy.CHARS_PER_TOKEN,
                  words * ContextMetricPolicy.WORDS_PER_TOKEN)
        return max(1, int(est))

    @staticmethod
    def compress_failure_message(error: Exception | None, attempts: int | None = None) -> str:
        n = attempts if attempts is not None else ContextMetricPolicy.COMPRESS_RETRY_ATTEMPTS
        return f"Compression failed after {n} attempts: {error}"