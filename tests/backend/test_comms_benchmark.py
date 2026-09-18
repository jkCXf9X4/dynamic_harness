"""P3 — the communication comparison bed: collaboration task + cell runner.

Verifies the bed is real and reproducible before any real-LLM probe:

- the collaboration task's verifier is mechanical (interdependent mode FAILS
  without cross-agent information);
- the per-cell ``runtime_factory`` builds the right comms backend per cell;
- two replicate runs with a deterministic (stub) LLM produce identical
  metrics — the bed adds no noise, so a later cell ranking is attributable to
  the topology, not the harness.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from dynamic_harness.benchmark.comms import CELLS, COLLAB_TASKS, run_cells, runtime_factory_for
from dynamic_harness.benchmark.tasks import CollaborationTask
from dynamic_harness.core.comms.backends.relay import RelayBackend
from dynamic_harness.core.comms.backends.shared import SharedBackend
from dynamic_harness.core.comms.backends.siblings import SiblingsBackend
from dynamic_harness.core.comms.backends.topics import TopicsBackend
from dynamic_harness.llm.provider import LLMConfig, LLMProvider, LLMResponse, ToolCallResponse


class _FixedLLM(LLMProvider):
    """Deterministic stub: always answers with plain text (no tool calls)."""

    default_model = "stub"

    async def generate(self, system, user, config: LLMConfig | None = None) -> LLMResponse:
        return LLMResponse(content="Deterministic outcome.", model="stub")

    async def generate_with_tools(
        self, messages, tools, config: LLMConfig | None = None
    ) -> ToolCallResponse:
        return ToolCallResponse(content="Deterministic outcome.", model="stub")

    async def generate_structured(self, system, user, response_model, config=None):
        return None


def _workspace(xs: dict[int, int]) -> Path:
    """Minimal scan root: resources/_collab/partN.txt + .optimize_benchmarks."""
    ws = Path(tempfile.mkdtemp(prefix="collab_ws_"))
    base = ws / "resources" / "_collab"
    base.mkdir(parents=True)
    for n, x in xs.items():
        (base / f"part{n}.txt").write_text(f"{x}\n")
    (ws / ".optimize_benchmarks").mkdir()
    return ws


def _write(ws: Path, lines: list[str]) -> None:
    (ws / ".optimize_benchmarks" / "collab.txt").write_text("\n".join(lines) + "\n")


# -- collaboration task verifier --------------------------------------------


def test_collab_verifier_independent():
    ws = _workspace({1: 3, 2: 5, 3: 2, 4: 7})
    _write(ws, ["y1=6", "y2=10", "y3=4", "y4=14"])
    task = CollaborationTask(mode="independent")
    ok, note = task.verify(ws / ".optimize_benchmarks", ws)
    assert ok, note


def test_collab_verifier_interdependent_requires_sharing():
    ws = _workspace({1: 3, 2: 5, 3: 2, 4: 7})
    task = CollaborationTask(mode="interdependent")
    # Own-only values (doubles) cannot satisfy the neighbor-dependent truth.
    _write(ws, ["y1=6", "y2=10", "y3=4", "y4=14"])
    ok, note = task.verify(ws / ".optimize_benchmarks", ws)
    assert not ok
    assert "wrong" in note or "missing" in note
    # Correct wrap-around sums pass.
    _write(ws, ["y4=10", "y1=8", "y2=7", "y3=9"])
    ok, note = task.verify(ws / ".optimize_benchmarks", ws)
    assert ok, note


def test_collab_verifier_missing_report():
    ws = _workspace({1: 3, 2: 5})
    task = CollaborationTask(mode="independent")
    ok, note = task.verify(ws / ".optimize_benchmarks", ws)
    assert not ok and "collab.txt missing" in note


# -- cell-parameterized factory ---------------------------------------------


def test_factory_off_has_no_comms():
    assert runtime_factory_for("off")().comms is None


@pytest.mark.parametrize(
    ("cell", "backend_cls"),
    [
        ("relay", RelayBackend),
        ("siblings", SiblingsBackend),
        ("shared", SharedBackend),
        ("topics_parent", TopicsBackend),
        ("topics_anarchic", TopicsBackend),
    ],
)
def test_factory_builds_cell_backend(cell: str, backend_cls):
    rt = runtime_factory_for(cell)()
    assert rt.comms is not None
    assert isinstance(rt.comms, backend_cls)


def test_factory_topics_parent_declares_channels():
    rt = runtime_factory_for("topics_parent")()
    assert rt.comms._policy.registration == "parent"
    assert "findings" in rt.comms._policy._allowed
    rt2 = runtime_factory_for("topics_anarchic")()
    assert rt2.comms._policy.registration == "anarchic"


def test_factory_rejects_unknown_cell():
    with pytest.raises(ValueError):
        runtime_factory_for("bogus")


# -- reproducibility ---------------------------------------------------------


@pytest.mark.asyncio
async def test_bed_reproducible_with_deterministic_llm():
    ws = _workspace({1: 3, 2: 5, 3: 2, 4: 7})
    results = await run_cells(
        COLLAB_TASKS[:1],  # independent mode only (no comms needed)
        llm=_FixedLLM(),
        cells=("off",),
        replicates=2,
        workspace=ws,
    )
    assert len(results) == 2
    m1, m2 = results
    # Every deterministic field is identical across replicates.
    for field in (
        "status", "correct", "verification_note", "total_tokens",
        "agent_count", "delegations", "total_turns", "message_count",
        "failures", "escalations",
    ):
        assert getattr(m1, field) == getattr(m2, field), field
    # The stub never writes the deliverable: mechanically wrong, deterministically so.
    assert m1.correct is False and m1.status == "completed"