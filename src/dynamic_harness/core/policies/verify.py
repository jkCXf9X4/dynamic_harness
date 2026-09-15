"""Verification policy as a composable policy object (G1).

gap-analysis.md G1: "VERIFY is prompt discipline, not a mechanism; acceptance
criteria are never checked." ``plan(acceptance=...)`` recorded the acceptance
terms but nothing mechanically evaluated them against the output. This policy
closes the mechanism half: ``plan`` must declare an objective + acceptance
terms, then — when a runtime turns on ``verify_children`` — a child's final
artifact is checked against those terms the way ``HealPolicy.deliverable_ok``
checks the file/deliverable gate.

The check is deliberately a *keyword/term scan* over the artifact body (the
"does the artifact mention the acceptance terms" gate the docs specify) — it
is mechanical, cheap, and independent of model prose. It returns a structured
``VerifyResult`` so a runtime can decide whether to nudge the child, escalate,
or accept.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re


@dataclass(frozen=True)
class VerifyResult:
    """Outcome of a ``VerifyPolicy.check`` call."""

    met: bool
    missing_terms: list[str] = field(default_factory=list)
    message: str = ""


class VerifyPolicy:
    """Decides whether a body of work satisfies its declared acceptance terms.

    Host-agnostic: an MCP verification hook or embedded host can apply the same
    scan without importing a runtime or agent.
    """

    #: Case-insensitive term matching (terms may be multi-word phrases).
    _WORD_SPLIT = re.compile(r"[^A-Za-z0-9_\-+.#]+")

    def __init__(self, *, require_missing_report: bool = True) -> None:
        # When a child declared acceptance terms but produced NO artifact body
        # to scan, the check fails (nothing to verify is not a pass).
        self.require_missing_report = require_missing_report

    def check(self, *, body: str, acceptance: list[str] | None) -> VerifyResult:
        terms = [t.strip() for t in (acceptance or []) if t and t.strip()]
        if not terms:
            return VerifyResult(met=True, message="no acceptance terms declared")
        body = body or ""
        if not body.strip():
            if self.require_missing_report:
                return VerifyResult(
                    met=False, missing_terms=terms,
                    message="no artifact body to verify against acceptance terms.",
                )
            return VerifyResult(met=True, message="no artifact body")
        lowered = body.lower()
        missing = [t for t in terms if not self._term_present(lowered, t)]
        if not missing:
            return VerifyResult(
                met=True,
                message=(
                    f"artifact mentions all {len(terms)} acceptance terms: "
                    + ", ".join(terms)
                ),
            )
        return VerifyResult(
            met=False,
            missing_terms=missing,
            message=(
                f"artifact does not mention acceptance term(s): {', '.join(missing)}. "
                "Ask the child to cover them (or delegate the missing piece) "
                "before synthesizing from its output."
            ),
        )

    @classmethod
    def _term_present(cls, lowered_body: str, term: str) -> bool:
        """True when a normalized term's words appear in the body (case-
        insensitive, whitespace-insensitive — a term is a bag of words that
        must all appear as whole words, not substrings)."""
        words = [w for w in cls._WORD_SPLIT.split(term.lower()) if w]
        if not words:
            return True
        body_words = set(cls._WORD_SPLIT.split(lowered_body))
        return all(w in body_words for w in words)