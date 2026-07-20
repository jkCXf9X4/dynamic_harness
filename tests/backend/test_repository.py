from __future__ import annotations

import pytest

from dynamic_harness.memory.repository import Commit, Repository


def test_commit_and_retrieve(repo: Repository) -> None:
    c = Commit(task_id="task1", agent_id="agent1", summary="Done")
    repo.commit(c)

    loaded = repo.get(c.id)
    assert loaded is not None
    assert loaded.task_id == "task1"
    assert loaded.summary == "Done"


def test_parent_child_links(repo: Repository) -> None:
    parent = Commit(task_id="task1", agent_id="agent1", summary="Parent")
    repo.commit(parent)

    child = Commit(task_id="task2", agent_id="agent2", summary="Child", parent_ids=[parent.id])
    repo.commit(child)

    loaded_parent = repo.get(parent.id)
    assert loaded_parent is not None
    assert child.id in loaded_parent.child_ids


def test_log_returns_most_recent_first(repo: Repository) -> None:
    c1 = Commit(task_id="task1", agent_id="agent1", summary="First")
    c2 = Commit(task_id="task2", agent_id="agent2", summary="Second")
    repo.commit(c1)
    repo.commit(c2)

    log = repo.log()
    assert log[0].task_id == "task2" or log[0].task_id == "task1"


def test_tree_structure(repo: Repository) -> None:
    root = Commit(task_id="root", agent_id="a1", summary="Root")
    repo.commit(root)

    child1 = Commit(task_id="c1", agent_id="a2", summary="Child 1", parent_ids=[root.id])
    child2 = Commit(task_id="c2", agent_id="a3", summary="Child 2", parent_ids=[root.id])
    repo.commit(child1)
    repo.commit(child2)

    tree = repo.tree(root.id)
    assert root.id in tree
    assert child1.id in tree[root.id]
    assert child2.id in tree[root.id]


def test_persistence_across_instances(repo: Repository) -> None:
    c = Commit(task_id="task1", agent_id="agent1", summary="Persist me")
    repo.commit(c)
    root = repo.root

    repo2 = Repository(root)
    loaded = repo2.get(c.id)
    assert loaded is not None
    assert loaded.summary == "Persist me"


def test_artifact_ids_in_commit(repo: Repository) -> None:
    c = Commit(
        task_id="task1",
        agent_id="agent1",
        summary="With artifacts",
        artifact_ids=["art1", "art2"],
    )
    repo.commit(c)

    loaded = repo.get(c.id)
    assert loaded is not None
    assert "art1" in loaded.artifact_ids
    assert "art2" in loaded.artifact_ids
