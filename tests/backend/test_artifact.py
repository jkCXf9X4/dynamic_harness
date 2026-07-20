from __future__ import annotations

from pathlib import Path

import pytest

from dynamic_harness.artifact.store import Artifact, ArtifactStore, ArtifactView


def test_save_and_get_artifact(store: ArtifactStore) -> None:
    view = ArtifactView(headline="Test result", summary_200="Test result details")
    art = Artifact(task_id="task1", agent_id="agent1", views=view)
    store.save(art)

    loaded = store.get(art.id)
    assert loaded is not None
    assert loaded.task_id == "task1"
    assert loaded.agent_id == "agent1"
    assert loaded.views.headline == "Test result"


def test_progressive_disclosure_views(store: ArtifactStore) -> None:
    view = ArtifactView(
        headline="Bug found",
        summary_200="Parser fails on nested generics.",
        summary_1000="The parser fails when encountering nested generic types in certain edge cases.",
        technical="Full technical analysis...",
        full_report="Complete report with all details...",
    )
    art = Artifact(task_id="task1", agent_id="agent1", views=view)
    store.save(art)

    assert art.get_view("headline") == "Bug found"
    assert art.get_view("summary_200") == "Parser fails on nested generics."
    assert art.get_view("summary_1000") == "The parser fails when encountering nested generic types in certain edge cases."
    assert art.get_view("technical") == "Full technical analysis..."
    assert art.get_view("full_report") == "Complete report with all details..."


def test_write_and_read_text_file(store: ArtifactStore) -> None:
    art = Artifact(task_id="task1", agent_id="agent1")
    store.save(art)

    store.write_text(art.id, "report.md", "# Research Report\nFindings here.")
    content = store.read_text(art.id, "report.md")
    assert content == "# Research Report\nFindings here."


def test_list_files(store: ArtifactStore) -> None:
    art = Artifact(task_id="task1", agent_id="agent1")
    store.save(art)

    store.write_text(art.id, "report.md", "content")
    store.write_text(art.id, "data.json", '{"key": "value"}')

    files = store.list_files(art.id)
    names = {f.name for f in files}
    assert "report.md" in names
    assert "data.json" in names


def test_persistence_across_instances(tmp: Path) -> None:
    store1 = ArtifactStore(tmp)
    art = Artifact(task_id="task1", agent_id="agent1", views=ArtifactView(headline="Persisted"))
    store1.save(art)

    store2 = ArtifactStore(tmp)
    loaded = store2.get(art.id)
    assert loaded is not None
    assert loaded.views.headline == "Persisted"


def test_clear_removes_disk_artifacts(store: ArtifactStore) -> None:
    art = Artifact(task_id="task1", agent_id="agent1")
    store.save(art)
    artifact_dir = store._artifact_dir(art.id)
    assert artifact_dir.exists()

    store.clear()

    assert not artifact_dir.exists()
    assert store.get(art.id) is None
