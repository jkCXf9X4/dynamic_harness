from __future__ import annotations

import pytest

from dynamic_harness.artifact.store import Artifact, ArtifactView
from dynamic_harness.artifact.summary import hierarchical_summary, summarize_artifact


def _make_artifact(
    art_id: str = "art-1",
    headline: str = "Test headline",
    summary_200: str = "Short summary under 200 chars.",
    summary_1000: str = "",
    technical: str = "",
    full_report: str = "",
) -> Artifact:
    return Artifact(
        id=art_id,
        task_id="task-1",
        agent_id="agent-1",
        views=ArtifactView(
            headline=headline,
            summary_200=summary_200,
            summary_1000=summary_1000,
            technical=technical,
            full_report=full_report,
        ),
    )


class TestSummarizeArtifact:
    def test_target_200_uses_headline(self) -> None:
        art = _make_artifact(headline="Headline result")
        result = summarize_artifact(art, target_tokens=200)
        assert result == "Headline result"

    def test_target_200_falls_back_to_summary_200(self) -> None:
        art = _make_artifact(headline="", summary_200="Summary 200 fallback")
        result = summarize_artifact(art, target_tokens=200)
        assert result == "Summary 200 fallback"

    def test_target_500_uses_summary_1000(self) -> None:
        art = _make_artifact(summary_1000="Medium-length summary for 1000 chars.")
        result = summarize_artifact(art, target_tokens=500)
        assert result == "Medium-length summary for 1000 chars."

    def test_target_500_falls_back_to_summary_200(self) -> None:
        art = _make_artifact(summary_200="Fallback to 200")
        result = summarize_artifact(art, target_tokens=500)
        assert result == "Fallback to 200"

    def test_target_2000_uses_technical(self) -> None:
        art = _make_artifact(technical="Detailed technical analysis")
        result = summarize_artifact(art, target_tokens=2000)
        assert result == "Detailed technical analysis"

    def test_target_2000_falls_back_to_summary_1000(self) -> None:
        art = _make_artifact(summary_1000="Fallback to 1000")
        result = summarize_artifact(art, target_tokens=2000)
        assert result == "Fallback to 1000"


class TestHierarchicalSummary:
    def test_basic_structure(self) -> None:
        art = _make_artifact("art-1", headline="Finding 1")
        result = hierarchical_summary([art], level_name="executive")
        assert "# Executive Summary" in result
        assert "## Artifact art-1" in result
        assert "Finding 1" in result

    def test_includes_technical_when_present(self) -> None:
        art = _make_artifact(
            "art-1",
            headline="Finding",
            technical="This is a technical detail about the finding.",
        )
        result = hierarchical_summary([art])
        assert "Technical:" in result

    def test_skips_technical_when_empty(self) -> None:
        art = _make_artifact("art-1", headline="Finding")
        result = hierarchical_summary([art])
        assert "Technical:" not in result

    def test_respects_max_items(self) -> None:
        arts = [
            _make_artifact(f"art-{i}", headline=f"Finding {i}")
            for i in range(20)
        ]
        result = hierarchical_summary(arts, max_items=5)
        art_count = result.count("## Artifact art-")
        assert art_count == 5

    def test_level_name_title_cased(self) -> None:
        art = _make_artifact("art-1", headline="Finding")
        result = hierarchical_summary([art], level_name="detailed_technical")
        assert "# Detailed Technical Summary" in result

    def test_multiple_artifacts(self) -> None:
        arts = [
            _make_artifact("art-1", headline="Finding A"),
            _make_artifact("art-2", headline="Finding B"),
            _make_artifact("art-3", headline="Finding C"),
        ]
        result = hierarchical_summary(arts)
        assert "Finding A" in result
        assert "Finding B" in result
        assert "Finding C" in result

    def test_technical_preview_truncated(self) -> None:
        art = _make_artifact(
            "art-1",
            headline="Finding",
            technical="x" * 300,
        )
        result = hierarchical_summary([art])
        assert "Technical: " + "x" * 200 in result