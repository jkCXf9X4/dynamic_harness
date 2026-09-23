"""Cell-parameterized communication comparison bed (P3).

The cell is the ONLY variable: the same collaboration task(s), the same LLM,
and — apart from the runtime's ``communication`` config — identical runtimes.
Each topology cell is built by a per-cell ``runtime_factory``, reusing
``benchmark.runner.run_one`` + ``MetricsCollector`` so the five-axis battery
(completion / quality / cost / context-health / contention) comes out of the
box.

Cells (see ``../../../product-breakdown/04-verification/communication-structures/plan/README.md``):

- ``off``              — baseline: no comms layer (today's global by-ID converse)
- ``relay``            — cell 1: parent-mediated
- ``siblings``         — cell 2: same-parent peers
- ``shared``           — cell 3: one shared channel
- ``topics_parent``    — cell 4, parent-authorized registration
- ``topics_anarchic``  — cell 4, anarchic registration (sprawl probe)

The collaboration tasks live here (not ``ALL_TASKS`` — bed-specific).
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Callable

from ..config import HarnessConfig
from ..core.runtime import Runtime
from .metrics import MetricsCollector
from .runner import run_one
from .tasks import BenchmarkTask, CollaborationTask

CELLS: tuple[str, ...] = (
    "off",
    "relay",
    "siblings",
    "shared",
    "topics_parent",
    "topics_anarchic",
)

#: Bed tasks: the interdependent collaboration case + its independent control.
COLLAB_TASKS: list[BenchmarkTask] = [
    CollaborationTask(mode="independent"),
    CollaborationTask(mode="interdependent"),
]


def runtime_factory_for(
    cell: str, llm: object | None = None, trace_root: Path | None = None
) -> Callable[[], Runtime]:
    """Build a fresh Runtime for ``cell`` (a fresh backend + empty channel store).

    ``llm``, when given, is injected via ``set_llm``; the provider is reused
    across runs (it is a stateless API client — callers own ``aclose``).
    ``trace_root``, when given, is used as the runtime's JSONL trace store root
    (per-agent trace files aid diagnosis of slow/flaky real-LLM runs).
    """
    if cell not in CELLS:
        raise ValueError(
            f"unknown cell {cell!r} (use one of {', '.join(CELLS)})"
        )
    config = HarnessConfig()
    comms = config.communication
    if cell == "relay":
        comms.topology = "relay"
    elif cell == "siblings":
        comms.topology = "siblings"
    elif cell == "shared":
        comms.topology = "shared"
    elif cell == "topics_parent":
        comms.topology = "topics"
        comms.registration = "parent"
        comms.channels = ["findings"]
    elif cell == "topics_anarchic":
        comms.topology = "topics"
        comms.registration = "anarchic"
    # "off" keeps the defaults: no comms layer.

    def build() -> Runtime:
        base = Path(tempfile.mkdtemp(prefix=f"cell_{cell}_"))
        rt = Runtime(
            artifact_root=base / "artifacts",
            repo_root=base / "repo",
            trace_root=trace_root,
            generated_root=base / "gen",
            config=config,
        )
        if llm is not None:
            rt.set_llm(llm)
        return rt

    return build


async def run_cells(
    tasks: list[BenchmarkTask],
    *,
    llm: object,
    cells: tuple[str, ...] = CELLS,
    replicates: int = 1,
    workspace: Path | None = None,
    collector: MetricsCollector | None = None,
) -> list:
    """Run ``tasks`` across every cell × replicate, returning ``RunMetrics``.

    ``prompt_id`` is set to ``<cell>#rep<N>`` so the five-axis report can group
    by cell. Uses the caller's workspace when given; otherwise each run stages
    its own via ``run_one``'s default (the current working directory).
    """
    collector = collector or MetricsCollector()
    results = []
    for cell in cells:
        factory = runtime_factory_for(cell, llm=llm)
        for rep in range(replicates):
            for task in tasks:
                outcome = await run_one(
                    runtime_factory=factory,
                    task=task,
                    prompt_id=f"{cell}#rep{rep}",
                    collector=collector,
                    workspace=workspace,
                )
                results.append(outcome.metrics)
    return results