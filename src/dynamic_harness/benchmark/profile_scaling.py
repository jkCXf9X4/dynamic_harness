"""Empirical scaling profiler for the runtime's own per-turn / per-agent overhead.

Each agent is supposed to stay "contained" (prune/compress/window bound the LLM
prompt), yet overall wall-clock time still grows superlinearly as conversations
lengthen and agent counts rise. That remaining growth is *bookkeeping* overhead,
not LLM prompting cost — and most of it is not proportional to the size of the
prompt sent to the model.

This script measures, in isolation and with a **mock LLM (no network)**, the
scaling behaviour of the hot paths most likely to explain that grow:

  A. ``persist_checkpoint()`` — serializes + writes the WHOLE conversation to
     disk after every committed turn. Cost grows with total accumulated bytes,
     so a long conversation pays O(t) per turn and O(t^2) overall.
  B. ``Repository.commit()`` -> ``_flush()`` — rewrites the ENTIRE commits.jsonl
     on every commit. Each terminating agent commits, so N agents cost O(N) per
     commit and O(N^2) overall.
  C. CLI ``StateWriter.snapshot()`` -> ``build_agent_tree()`` -> ``provenance()``
     — rebuilds the whole tree (and re-sorts every commit) on every terminal
     event, once per artifact-emitting agent. Compounds axes A and B.

It prints shading tables: size -> per-unit time -> scaling ratio vs. linear. A
ratio near 1.0 = linear (fine); a ratio that climbs with size = superlinear
(that axis is a suspect). See docs/guides/performance-diagnostics.md for the
methodology and how to read the output.

Usage:
  python -m dynamic_harness.benchmark.profile_scaling [--quick] [--out PATH]
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from ..core.agent import Agent
from ..core.context import AgentContext
from ..core.runtime import Runtime
from ..core.task import ReportPayload, Task
from ..memory.repository import Commit, Repository
from ..llm.provider import LLMProvider, LLMResponse, ToolCallData, ToolCallResponse


# --------------------------------------------------------------------------- #
# Mock LLM (deterministic, local, no I/O past a small in-memory tap)          #
# --------------------------------------------------------------------------- #
class _TapProvider(LLMProvider):
    """Plays a scripted single-tool-call (bash) then a text "done".

    Mirrors a realistic chatty agent that performs one cheap tool call per turn,
    letting the run loop exercise persist_checkpoint/commit_turn/event cost
    without any network activity.
    """

    default_model = "profile-model"

    def __init__(self, n_turns: int) -> None:
        self._remaining = n_turns

    async def generate(self, system, user, config=None):
        return LLMResponse(content="ok", model=self.default_model)

    async def generate_structured(self, system, user, response_model, config=None):
        raise NotImplementedError

    async def generate_with_tools(self, messages, tools, config=None):
        if self._remaining > 0:
            self._remaining -= 1
            return ToolCallResponse(
                content="tick",
                tool_calls=[
                    ToolCallData(
                        id=f"c_{self._remaining}",
                        name="bash",
                        arguments={"command": "true"},
                    )
                ],
                model=self.default_model,
                usage={"prompt_tokens": 10, "completion_tokens": 5, "cached_tokens": 0},
            )
        return ToolCallResponse(
            content="done", tool_calls=None, model=self.default_model,
            usage={"prompt_tokens": 10, "completion_tokens": 2, "cached_tokens": 0},
        )

    async def aclose(self) -> None:
        pass


def _timeit(fn, *args, **kwargs) -> float:
    """Return wall-clock seconds for one call of ``fn``."""
    t0 = time.perf_counter()
    fn(*args, **kwargs)
    return time.perf_counter() - t0


def _print_table(rows: list[tuple[list, ...]], headers: list[str]) -> None:
    """Print a right-aligned column table with a shading column last."""
    str_rows = [[str(c) for c in r] for r in rows]
    widths = [
        max(len(h), *(len(r[i]) for r in str_rows))
        for i, h in enumerate(headers)
    ]
    header = "  ".join(h.rjust(w) for h, w in zip(headers, widths))
    print("  " + header)
    print("  " + "-" * len(header))
    for r in str_rows:
        print("  " + "  ".join(c.rjust(w) for c, w in zip(r, widths)))
    print()


def _growth(ratio: float, linear_mult: float) -> str:
    """Classify growth vs the *linear* expectation, not just vs the first size.

    A true linear path has ratio ≈ linear_mult. Above that = superlinear
    (a suspect); below = sublinear (fine); around it = linear (fine).
    """
    if ratio > linear_mult * 1.3:
        return "superlinear"
    if ratio < linear_mult * 0.7:
        return "sublinear"
    return "linear"


# --------------------------------------------------------------------------- #
# A. Checkpoint persistence vs. conversation length                           #
# --------------------------------------------------------------------------- #
def _run_checkpoint_turns(ns: list[int]) -> None:
    print("\nA. persist_checkpoint() per turn (UNBOUNDED conversation kept on disk)")
    print("   Expected: linear time per turn => total O(t^2). Watch per-unit time climb.")
    headers = ["turns", "median ms", "ratio vs @500", "grows with turns?"]
    rows: list[tuple[list, ...]] = []
    baseline: float | None = None
    for n in ns:
        ms = []
        for _ in range(5):
            ctx = AgentContext()
            ctx.reset("system p", "user p")
            runtime = Runtime(
                artifact_root=Path.cwd() / ".profile-tmp" / "artifacts",
                repo_root=Path.cwd() / ".profile-tmp" / "repo",
            )
            agent = runtime.delegate(Task(description="profile"))
            for i in range(n):
                assistant = {
                    "role": "assistant", "content": f"step {i}",
                    "tool_calls": [
                        {
                            "id": f"c{i}", "type": "function",
                            "function": {
                                "name": "read",
                                "arguments": json.dumps({"path": f"/f/{i}"}),
                            },
                        }
                    ],
                }
                results = [{
                    "role": "tool", "tool_call_id": f"c{i}",
                    "content": f"result for step {i}: " + "x" * 120,
                }]
                ctx.commit_turn(assistant, results)
            # Time the LARGEST checkpoint (a full n-turn conversation), which is
            # the real per-turn cost an agent pays near the end of its run.
            ms.append(_timeit(agent.persist_checkpoint) * 1000)
        if baseline is None:
            baseline = sum(ms) / len(ms)
        ratio = 1.0 if baseline == 0 else (sum(ms) / len(ms)) / baseline
        rows.append([n, f"{sum(ms)/len(ms):.3f}", f"{ratio:.2f}x",
                     _growth(ratio, linear_mult=n / ns[0])])
    _print_table(rows, headers)


# --------------------------------------------------------------------------- #
# A2. Prompt actually SENT per turn (the LLM cost driver)                     #
# --------------------------------------------------------------------------- #
def _run_prompt_growth(ns: list[int], msg_bytes: int) -> None:
    print("\nA2. Bytes actually SENT to the LLM per turn (full history, no auto-prune)")
    print("   active_turn_window only trims the observation LIST, not the request.")
    print("   ag runs `sent = list(context.messages)` -> whole history goes every turn.")
    headers = ["turns", "messages", "est. prompt tokens", "payload KB", "vs @100"]
    rows: list[tuple[list, ...]] = []
    baseline: float | None = None
    for n in ns:
        ctx = AgentContext()
        ctx.reset("system prompt " * 40, "user task " * 20)
        blob = "d" * msg_bytes
        for i in range(n):
            assistant = {
                "role": "assistant", "content": f"assistant step {i} " + "z" * 80,
                "tool_calls": [
                    {
                        "id": f"c{i}", "type": "function",
                        "function": {
                            "name": "read",
                            "arguments": json.dumps({"path": f"/f/{i}", "pattern": "w" * 40}),
                        },
                    }
                ],
            }
            results = [{
                "role": "tool", "tool_call_id": f"c{i}", "content": blob,
            }]
            ctx.commit_turn(assistant, results)
        payload = sum(len(json.dumps(m)) for m in ctx.messages)
        tokens = ctx.estimate_prompt_tokens()
        if baseline is None:
            baseline = payload
        rows.append([n, len(ctx.messages), tokens, f"{payload/1024:.1f}",
                     f"{payload/baseline:.2f}x" if baseline else "1.00x"])
    _print_table(rows, headers)


# --------------------------------------------------------------------------- #
# B. Repository flush vs. commit count                                        #
# --------------------------------------------------------------------------- #
def _run_commit_flush(ns: list[int]) -> None:
    print("\nB. Repository.commit() -> full commits.jsonl rewrite")
    print("   Expected: O(N) per commit => O(N^2) across a many-agent run.")
    headers = ["commits", "median ms", "ratio vs @50", "grows with agents?"]
    rows: list[tuple[list, ...]] = []
    baseline: float | None = None
    for n in ns:
        tm: list[float] = []
        for _ in range(5):
            with TemporaryDirectory() as d:
                repo = Repository(Path(d) / "repo")
                for i in range(n):
                    c = Commit(
                        task_id=f"t{i}", agent_id=f"a{i}",
                        summary="s" * 40,
                        artifact_ids=[f"art{i}"],
                    )
                    tm.append(_timeit(repo.commit, c))
        if baseline is None:
            baseline = sum(tm) / len(tm)
        ratio = (sum(tm) / len(tm)) / baseline
        rows.append([n, f"{sum(tm)/len(tm):.3f}", f"{ratio:.2f}x",
                     _growth(ratio, linear_mult=n / ns[0])])
    _print_table(rows, headers)


# --------------------------------------------------------------------------- #
# C. CLI snapshot (agent tree + provenance) vs. agent count                   #
# --------------------------------------------------------------------------- #
def _build_snapshot_runtime(n: int, root: Path) -> Runtime:
    """Runtime with ``n`` completed leaf agents committing real artifacts."""
    rt = Runtime(
        artifact_root=root / "artifacts",
        repo_root=root / "repo",
        generated_root=root,
    )

    swallow = root / "swallow"
    swallow.mkdir(parents=True, exist_ok=True)
    f = swallow / "out.txt"
    f.write_text("x" * 300)

    for i in range(n):
        agent = rt.delegate(Task(description=f"leaf {i}"))
        rt.deliver_report(agent.id, ReportPayload(
            task_id=agent.task.id,
            summary=f"leaf {i} done",
            full_report="full " * 40,
            files_written=[str(f)],
        ))
    return rt


def _run_cli_snapshot(ns: list[int]) -> None:
    from ..cli.present import build_agent_tree
    from ..cli.state import StateWriter

    print("\nC. CLI StateWriter.snapshot() (agent tree built ONCE + provenance index)")
    print("   Fixed: tree built once; provenance resolved in one O(N) index pass.")
    headers = ["agents", "median ms", "ratio vs @10", "grows with agents?"]
    rows: list[tuple[list, ...]] = []
    baseline: float | None = None
    for n in ns:
        tm: list[float] = []
        for _ in range(4):
            with TemporaryDirectory() as d:
                rt = _build_snapshot_runtime(n, Path(d))
                writer = StateWriter(Path(d) / "run")
                tm.append(_timeit(writer.snapshot, rt) * 1000)
        if baseline is None:
            baseline = sum(tm) / len(tm)
        ratio = (sum(tm) / len(tm)) / baseline
        rows.append([n, f"{sum(tm)/len(tm):.3f}", f"{ratio:.2f}x",
                     _growth(ratio, linear_mult=n / ns[0])])
    _print_table(rows, headers)


# --------------------------------------------------------------------------- #
# D. Full run loop with a real (but local) agent                              #
# --------------------------------------------------------------------------- #
def _run_full_runloop(ns: list[int]) -> None:
    import asyncio

    print("\nD. Full Agent.run() loop (mock LLM, 1 tool call per turn)")
    print("   Could not use a marking column; prints wall time at conversation size.")

    async def run_one(n: int) -> float:
        with TemporaryDirectory() as d:
            rt = Runtime(
                artifact_root=Path(d) / "artifacts",
                repo_root=Path(d) / "repo",
                generated_root=Path(d),
            )
            # Every turn writes a checkpoint; verify the checkpoint file grows.
            rt.set_llm(_TapProvider(n))
            task = Task(description="profile run")
            agent = rt.delegate(task)
            t0 = time.perf_counter()
            await agent.run()
            return time.perf_counter() - t0

    headers = ["turns", "wall s", "per-turn ms", "ratio vs @10"]
    rows: list[tuple[list, ...]] = []
    baseline: float | None = None
    for n in ns:
        t = asyncio.run(run_one(n))
        per_turn = t / n * 1000
        if baseline is None:
            baseline = per_turn
        ratio = per_turn / baseline
        rows.append([n, f"{t:.3f}", f"{per_turn:.2f}", f"{ratio:.2f}x"])
    _print_table(rows, headers)


def main() -> None:
    parser = argparse.ArgumentParser(description="Empirical scaling profiler")
    parser.add_argument("--quick", action="store_true",
                        help="smaller grid for a faster sanity pass")
    args = parser.parse_args()

    if args.quick:
        turns = [100, 200, 400, 800]
        commits = [50, 100, 200, 400]
        agents = [10, 20, 40, 80]
        loops = [10, 20, 40, 80]
    else:
        turns = [100, 200, 400, 800, 1600, 3200]
        commits = [25, 50, 100, 200, 400, 800]
        agents = [10, 20, 40, 80, 160, 320]
        loops = [10, 20, 40, 80, 160]

    import shutil
    shutil.rmtree(".profile-tmp", ignore_errors=True)

    _run_checkpoint_turns(turns)
    # 160-byte tool results: a modest, realistic per-turn payload.
    _run_prompt_growth(turns[:6], msg_bytes=160)
    _run_commit_flush(commits)
    _run_cli_snapshot(agents)
    _run_full_runloop(loops)

    shutil.rmtree(".profile-tmp", ignore_errors=True)
    print("\nDone. Lines whose 'ratio' climbs with size mark superlinear axes.")
    print("See docs/guides/performance-diagnostics.md for interpretation.")


if __name__ == "__main__":
    main()
