from __future__ import annotations

import asyncio
import json

import pytest

from dynamic_harness.core.agent import Agent
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import ReportPayload, Task


@pytest.mark.asyncio
async def test_default_agent_runtime(runtime: Runtime) -> None:
    root_task = Task(description="Default agent test")
    root = runtime.delegate(root_task)
    await root.run()

    assert root.task.status.value == "failed"
    assert "No LLM provider configured" in root.last_failure.error
    assert runtime.agent_count() >= 1


@pytest.mark.asyncio
async def test_runtime_tracks_task_graph(runtime: Runtime) -> None:
    class LeafAgent(Agent):
        async def run(self) -> None:
            self.report(ReportPayload(
                task_id=self.task.id,
                summary="Leaf done",
            ))

    runtime.register_agent_class("LeafAgent", LeafAgent)

    root = runtime.delegate(Task(description="Root"), agent_type="LeafAgent")
    a = root.delegate("A", agent_type="LeafAgent")
    b = root.delegate("B", agent_type="LeafAgent")

    graph = runtime.task_graph()
    assert a.id in graph[root.id]
    assert b.id in graph[root.id]


@pytest.mark.asyncio
async def test_artifact_store_populated_on_report(runtime: Runtime) -> None:
    class LeafAgent(Agent):
        async def run(self) -> None:
            self.report(ReportPayload(
                task_id=self.task.id,
                summary="Populated",
            ))

    runtime.register_agent_class("LeafAgent", LeafAgent)

    root = runtime.delegate(Task(description="Populate"), agent_type="LeafAgent")
    await root.run()

    commits = runtime.repository.log()
    for c in commits:
        for aid in c.artifact_ids:
            art = runtime.artifact_store.get(aid)
            assert art is not None, f"Artifact {aid} not found in store"


@pytest.mark.asyncio
async def test_runtime_event_handlers(runtime: Runtime) -> None:
    events: list[str] = []

    runtime.on_report(lambda aid, p: events.append(f"report:{aid[:8]}"))
    runtime.on_failure(lambda aid, f: events.append(f"fail:{aid[:8]}"))

    class LeafAgent(Agent):
        async def run(self) -> None:
            self.report(ReportPayload(
                task_id=self.task.id,
                summary="Test events",
            ))

    runtime.register_agent_class("LeafAgent", LeafAgent)
    root = runtime.delegate(Task(description="Events"), agent_type="LeafAgent")
    await root.run()

    assert any("report:" in e for e in events)


@pytest.mark.asyncio
async def test_unknown_agent_type_uses_default(runtime: Runtime) -> None:
    root = runtime.delegate(Task(description="Unknown type"), agent_type="Anything")
    await root.run()
    assert root.task.status.value == "failed"
    assert runtime.agent_count() >= 1


@pytest.mark.asyncio
async def test_concurrent_children_reports_keep_repo_consistent(runtime: Runtime) -> None:
    """Parallel children reporting simultaneously must not corrupt the repository
    tree or lose provenance links."""

    class LeafAgent(Agent):
        async def run(self) -> None:
            self.report(ReportPayload(
                task_id=self.task.id,
                summary=f"leaf {self.task.description}",
            ))

    class BranchAgent(Agent):
        async def run(self) -> None:
            a = self.delegate("A", agent_type="LeafAgent")
            b = self.delegate("B", agent_type="LeafAgent")
            await asyncio.gather(a.run(), b.run())
            self.report(ReportPayload(
                task_id=self.task.id,
                summary="branch",
            ))

    runtime.register_agent_class("LeafAgent", LeafAgent)
    runtime.register_agent_class("BranchAgent", BranchAgent)

    root = runtime.delegate(Task(description="Root"), agent_type="BranchAgent")
    await root.run()

    root_commit = runtime.repository.commit_for_task(root.task.id)
    assert root_commit is not None
    assert len(root_commit.child_ids) == 2, f"expected 2 children, got {root_commit.child_ids}"

    child_agents = [runtime.get_agent(c) for c in runtime.task_graph()[root.id]]
    for child in child_agents:
        assert child is not None
        child_commit = runtime.repository.commit_for_task(child.task.id)
        assert child_commit is not None
        assert root_commit.id in child_commit.parent_ids

    tree = runtime.repository.tree(root_commit.id)
    assert root_commit.id in tree
    assert set(tree[root_commit.id]) == set(root_commit.child_ids)
    assert runtime.repository.count() == 3


@pytest.mark.asyncio
async def test_provenance_maps_agent_to_artifacts_and_trace(tmp_path) -> None:
    artifact_root = tmp_path / "artifacts"
    repo_root = tmp_path / "repo"
    trace_root = tmp_path / "traces"
    runtime = Runtime(
        artifact_root=artifact_root, repo_root=repo_root,
        trace_root=trace_root, generated_root=tmp_path,
    )

    class LeafAgent(Agent):
        async def run(self) -> None:
            self.report(ReportPayload(
                task_id=self.task.id, summary="hello world", full_report="FULL BODY",
            ))

    runtime.register_agent_class("LeafAgent", LeafAgent)
    root = runtime.delegate(Task(description="provenance"), agent_type="LeafAgent")
    await root.run()

    (trace_root / root.id).mkdir(parents=True, exist_ok=True)
    (trace_root / root.id / "trace.jsonl").write_text("{}")

    prov = runtime.provenance(root.id)
    assert prov["task_id"] == root.task.id
    assert len(prov["artifact_ids"]) == 1
    aid = prov["artifact_ids"][0]
    assert prov["artifact_paths"][0] == str(artifact_root / aid)
    assert prov["trace_path"] == str(trace_root / root.id / "trace.jsonl")
    assert prov["commit_ids"]
    # The artifact really exists on disk and holds the report.
    assert (artifact_root / aid / "artifact.json").exists()
    assert runtime.artifact_store.get(aid) is not None


def test_write_provenance_index_round_trips(tmp_path) -> None:
    artifact_root = tmp_path / "artifacts"
    runtime = Runtime(
        artifact_root=artifact_root, repo_root=tmp_path / "repo",
        generated_root=tmp_path,
    )
    class LeafAgent(Agent):
        async def run(self) -> None:
            self.report(ReportPayload(task_id=self.task.id, summary="indexed"))

    runtime.register_agent_class("LeafAgent", LeafAgent)
    root = runtime.delegate(Task(description="idx"), agent_type="LeafAgent")
    asyncio.run(root.run())

    out = runtime.write_provenance_index(tmp_path / "index.jsonl")
    rows = [json.loads(ln) for ln in out.read_text().splitlines() if ln.strip()]
    assert len(rows) == 1
    row = rows[0]
    assert row["agent_id"] == root.id
    assert row["task_id"] == root.task.id
    assert row["path"] == str(artifact_root / row["artifact_id"])
    assert row["headline"] == "indexed"


@pytest.mark.asyncio
async def test_collect_garbage_reclaims_terminal_context_preserves_outcome(
    runtime: Runtime,
) -> None:
    class LeafAgent(Agent):
        async def run(self) -> None:
            self.context.append(
                {"role": "assistant", "content": "a large in-context payload"}
            )
            self.report(ReportPayload(
                task_id=self.task.id, summary="done", full_report="full body",
            ))

    runtime.register_agent_class("LeafAgent", LeafAgent)
    leaf = runtime.delegate(Task(description="leaf"), agent_type="LeafAgent")
    await leaf.run()

    assert leaf.task.status.value == "completed"
    assert leaf._context_freed is False
    assert len(leaf.context.messages) > 0  # the seeded in-context payload

    freed = runtime.collect_garbage(leaf.id)
    assert freed == 1
    assert leaf._context_freed is True
    assert leaf.context.messages == []
    assert leaf.context.turns == {}
    # Outcome (the lightweight result) is retained for the parent to consume.
    assert leaf.last_report is not None
    assert leaf.last_report.summary == "done"
    assert leaf.last_report.full_report == "full body"
    # Idempotent: a second pass reports nothing new.
    assert runtime.collect_garbage(leaf.id) == 0


@pytest.mark.asyncio
async def test_collect_garbage_leaves_running_agents_untouched(runtime: Runtime) -> None:
    running = runtime.delegate(Task(description="still going"))
    assert running._has_run is False
    assert runtime.collect_garbage(running.id) == 0
    assert running._context_freed is False


@pytest.mark.asyncio
async def test_run_auto_collects_descendants_preserves_root(runtime: Runtime) -> None:
    class LeafAgent(Agent):
        async def run(self) -> None:
            self.context.append(
                {"role": "assistant", "content": "leaf context payload"}
            )
            self.report(ReportPayload(task_id=self.task.id, summary="leaf done"))

    class BranchAgent(Agent):
        async def run(self) -> None:
            leaf = self.delegate("leaf", agent_type="LeafAgent")
            await leaf.run()
            self.report(ReportPayload(task_id=self.task.id, summary="branch done"))

    runtime.register_agent_class("LeafAgent", LeafAgent)
    runtime.register_agent_class("BranchAgent", BranchAgent)

    root = await runtime.run("root", agent_type="BranchAgent")

    # Descendants are reclaimed automatically once the run settles; the active
    # root is preserved so the interactive caller can still continue/inspect it.
    leaf = next(
        ag for aid, ag in runtime.all_agents().items() if aid != root.id
    )
    assert leaf._context_freed is True
    assert leaf.context.messages == []
    # The root stays resident (preserve_active_root) and its result is intact.
    assert root._context_freed is False
    assert root.last_report is not None
    assert root.last_report.summary == "branch done"


