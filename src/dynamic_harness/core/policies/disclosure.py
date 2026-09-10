"""Progressive-disclosure policy as a composable policy object.

The ``ArtifactView`` tiers (headline / summary_200 / summary_1000 / technical /
full_report / raw_data) were built and selected in FOUR places with slightly
different fallbacks — ``Runtime.deliver_report``, the ``archive`` tool, the
``read_artifact`` tool, and ``artifact/summary.py``. This policy is the single
owner of:

- how a report/payload is reduced into the view tiers (``views_from_report``),
- how a one-line/disclosure level maps onto view fields (``VIEW_LEVELS``),
- how a view is selected for a requested level, falling back to deeper content
  when a preview is empty (``select_level`` / ``Summarizer``).

Host-agnostic: an MCP artifact server or embedded host reusing the artifact
store gets the same disclosure decisions without importing a runtime or agent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..artifact.store import Artifact


#: Order in which deeper tiers are probed for the progressive fallback
#: (matches the historical read_artifact order: technical → full_report →
#: raw_data).
TIER_ORDER: tuple[str, ...] = (
    "technical",
    "full_report",
    "raw_data",
    "summary_1000",
    "summary_200",
    "headline",
)


class DisclosurePolicy:
    """Decides how findings are reduced to disclosure tiers and re-selected.

    The 200/1000-char tiers are the "headline → 200-char → 1000-char → technical
    → full" ladder the whole artifact design turns on (progressive disclosure).
    Building and selecting the tiers in one place keeps the threshold decisions
    from drifting between the runtime and the tools.
    """

    #: Level name → view fields to reveal, in display order.
    VIEW_LEVELS: dict[str, tuple[str, ...]] = {
        "auto": ("headline", "summary_200", "summary_1000"),
        "headline": ("headline",),
        "summary": ("headline", "summary_200", "summary_1000"),
        "technical": ("technical",),
        "full": ("full_report",),
        "raw": ("raw_data",),
    }

    @classmethod
    def validate_level(cls, level: str | None) -> str | None:
        """Normalize+validate a user-supplied level; return the normalized name
        or ``None`` when unknown (caller owns the error message)."""
        level = (level or "auto").strip().lower()
        if level not in cls.VIEW_LEVELS:
            return None
        return level

    # -- view construction ------------------------------------------------

    @staticmethod
    def _summary_tiers(headline: str, summary_text: str) -> dict[str, str]:
        """The three cheap preview tiers from a headline + body.

        ``headline`` is the display headline (first line of a report's summary,
        or an archive's label), capped at 200 chars. ``summary_200`` is the body
        capped at 200 chars; ``summary_1000`` is only populated when the body
        exceeds 200 chars (so a short body does not duplicate the same text at
        two tiers).
        """
        return {
            "headline": (headline or "")[:200],
            "summary_200": summary_text[:200],
            "summary_1000": summary_text[:1000] if len(summary_text) > 200 else "",
        }

    @classmethod
    def build_view_dict(cls, *, headline: str, summary_text: str, technical: str = "",
                        full_report: str = "", raw_data: str = "") -> dict[str, str]:
        """The complete view dict from a headline + body + deeper tiers.

        Shared by report delivery and the ``archive`` tool so the tier decisions
        never drift between them.
        """
        tiers = cls._summary_tiers(headline, summary_text)
        tiers["technical"] = technical or ""
        tiers["full_report"] = full_report or ""
        tiers["raw_data"] = raw_data or ""
        return tiers

    @classmethod
    def views_from_report(cls, summary: str, *, technical: str = "",
                          full_report: str = "") -> dict[str, str]:
        """Reduce a report's summary to the view tier dict.

        ``summary`` is the concise findings body (its first line becomes the
        headline); ``technical`` / ``full_report`` are the deeper tiers passed
        through as-is.
        """
        summary_text = summary or ""
        headline = summary_text.split("\n", 1)[0].strip()
        return cls.build_view_dict(
            headline=headline,
            summary_text=summary_text,
            technical=technical,
            full_report=full_report,
        )

    # -- view selection ---------------------------------------------------

    @staticmethod
    def view_fields_for_level(level: str) -> tuple[str, ...]:
        """The view fields revealed at a normalized level."""
        return DisclosurePolicy.VIEW_LEVELS[level]

    @staticmethod
    def reveal_fields(artifact: "Artifact", level: str) -> list[tuple[str, str]]:
        """(field, content) pairs revealed at ``level``.

        Uses the artifact's own view object (the views' ``views`` dict keys map
        onto the tier names).
        """
        names = DisclosurePolicy.VIEW_LEVELS[level]
        views = artifact.views.views
        return [(name, views[name]) for name in names if views[name]]

    @staticmethod
    def first_deeper_content(artifact: "Artifact", *, below: str) -> str | None:
        """The first DEEPER view field with content, for progressive fallback.

        Returns the field name (e.g. ``"technical"``) when a preview level came
        back empty but a deeper tier exists, else ``None``.
        """
        deeper: tuple[str, ...] = tuple(
            n for n in TIER_ORDER if n not in DisclosurePolicy.VIEW_LEVELS[below]
        )
        views = artifact.views.views
        for name in deeper:
            if views.get(name):
                return name
        return None

    # -- summary helpers (artifact/summary.py) -----------------------------

    @staticmethod
    def pick_for_token_budget(artifact: "Artifact", target_tokens: int) -> str:
        """The single view field best matching a token budget (~200 / ~1000+)."""
        views = artifact.views.views
        if target_tokens <= 200:
            return views["headline"] or views["summary_200"]
        if target_tokens <= 1000:
            return views["summary_1000"] or views["summary_200"]
        return views["technical"] or views["summary_1000"]