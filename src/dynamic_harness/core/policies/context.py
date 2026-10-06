"""Context-management decisions as a composable policy object.

``AgentContext`` kept two implicit heuristics reason about the context: the
token-proxy (``chars / 3.8`` vs ``words * 1.5``) and the compress retry count.
The same proxy is needed by anyone rendering tool pages or estimating context
cost. This policy owns those numbers so a plugin host reusing the context or
paging decisions applies identical estimates.

The reactive half lives here too: when an agent's *live* context (what the next
provider call will actually send) nears its fill threshold, the escalation
ladder fires — a budgeted warning telling the agent to compact itself, then at
a hard threshold an auto-compact *directive* the host performs (the run loop's
compaction safe point). The threshold decisions + wording stay on the metrics
policy; the warning budget is per agent (``ContextFillPolicy``).
"""

from __future__ import annotations

from dataclasses import dataclass

from .interface import Observation, PromptInjection, ReactivePolicy


@dataclass(frozen=True)
class ContextFillDecision:
    """A context-fill warning to inject, or ``fire=False`` when none should."""

    fire: bool
    estimate: int = 0
    threshold: int = 0
    note: str | None = None


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

    # -- context-fill warning (the reactive half) --------------------------

    @staticmethod
    def context_fill_warning(
        *, prompt_token_estimate: int, threshold: int
    ) -> ContextFillDecision:
        """Fire when the live-context estimate reaches ``threshold``.

        ``threshold <= 0`` disables the feature (harness.json convention). An
        estimate of 0 means the host did not fill the observation field — never
        fire on unknown, so a plugin host that does not track context stays
        silent rather than being warned spuriously.
        """
        if threshold <= 0 or prompt_token_estimate <= 0:
            return ContextFillDecision(fire=False)
        if prompt_token_estimate < threshold:
            return ContextFillDecision(fire=False, estimate=prompt_token_estimate)
        return ContextFillDecision(
            fire=True,
            estimate=prompt_token_estimate,
            threshold=threshold,
            note=ContextMetricPolicy.context_fill_note(
                estimate=prompt_token_estimate, threshold=threshold
            ),
        )

    @staticmethod
    def context_fill_note(estimate: int, threshold: int) -> str:
        """The user-facing notice injected when the live context nears its cap."""
        return (
            "Your context is getting full: the live context your next call will "
            f"send is estimated at ~{estimate} tokens (fill threshold "
            f"{threshold}). Compact it now — prune stale committed turns with "
            "`prune` and/or compress the history with `compress` — instead of "
            "starting new broad reads. Finish whatever is naturally closable, "
            "report, and let a fresh sub-agent re-read from disk if the material "
            "is needed."
        )

    @staticmethod
    def compress_failure_message(error: Exception | None, attempts: int | None = None) -> str:
        n = attempts if attempts is not None else ContextMetricPolicy.COMPRESS_RETRY_ATTEMPTS
        return f"Compression failed after {n} attempts: {error}"


class ContextFillPolicy(ReactivePolicy):
    """Per-agent context-fill escalation ladder (the reactive half of the
    context metrics).

    ``ContextMetricPolicy`` owns the threshold *decisions* and wording and the
    token proxies; this policy wraps the shared metrics policy for its
    decisions and owns one agent's warning budget, so it registers in an
    agent's reactive-policy registry like any other ``ReactivePolicy`` — and a
    plugin host drives it identically.

    The ladder (hard threshold first, then soft):

    - at or above ``compact_threshold`` — an auto-compact *directive*
      (``action="compact"``): the host sets the run loop's compaction event so
      the context is LLM-compressed at the next safe point — after queued
      input drains, before the next provider call, so the fat call is never
      made. The directive carries no message: the ``[Context compressed]``
      marker the summarization leaves behind is the agent-visible record.
      NOT budgeted — a compaction drops the estimate below the threshold, so
      it self-limits; a context that regrows past the threshold is exactly
      when it should fire again.
    - at or above ``fill_threshold`` (and below the compact threshold) — the
      soft near-full *warning*, budgeted: fires at most ``warning_attempts``
      times, telling the agent to ``prune`` / ``compress`` itself.

    The thresholds are read as an independent pair: when the compact threshold
    is at or below the warning threshold the compact branch owns everything at
    or above it and the soft warning never fires (its zone is empty). An
    estimate of 0 (an observation built without ``prompt_token_estimate`` — a
    host that does not track it) never fires either branch.
    """

    name: str = "context_fill"

    def __init__(
        self,
        *,
        fill_threshold: int = 100_000,
        compact_threshold: int = 240_000,
        warning_attempts: int = 2,
    ) -> None:
        self.fill_threshold: int = max(int(fill_threshold), 0)
        self.compact_threshold: int = max(int(compact_threshold), 0)
        self.warning_attempts: int = max(int(warning_attempts), 0)
        self.warning_left: int = self.warning_attempts

    def reset(self) -> None:
        """Restore the warning budget (fresh run / interactive resume)."""
        self.warning_left = self.warning_attempts

    def evaluate(self, observation: Observation) -> list[PromptInjection]:
        """React to an observation: the auto-compact directive when the
        estimate is at or above the compact threshold, else the budgeted
        near-full warning when it is at or above the fill threshold."""
        estimate = observation.prompt_token_estimate
        if estimate <= 0:
            return []
        if self.compact_threshold > 0 and estimate >= self.compact_threshold:
            return [PromptInjection(
                message="",
                level="notice",
                warning_type="context_auto_compact",
                data={"estimate": estimate, "threshold": self.compact_threshold},
                action="compact",
            )]
        if self.fill_threshold > 0 and estimate >= self.fill_threshold:
            if self.warning_left <= 0:
                return []
            self.warning_left -= 1
            d = ContextMetricPolicy.context_fill_warning(
                prompt_token_estimate=estimate,
                threshold=self.fill_threshold,
            )
            return [
                PromptInjection.warning(
                    d.note or "",
                    warning_type="context_fill",
                    data={
                        "estimate": d.estimate,
                        "threshold": d.threshold,
                        "attempts_remaining": self.warning_left,
                    },
                )
            ]
        return []