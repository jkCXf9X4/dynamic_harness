from __future__ import annotations

import asyncio
import json
import time as _time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable
from uuid import uuid4

from ..artifact.store import Artifact, ArtifactStore, ArtifactView
from ..memory.repository import Commit, Repository
from .agent import Agent
from .checkpoint import AgentCheckpoint, CheckpointStore
from .environment import EnvironmentInfo, build_environment_info
from .prompts import FocusLedger
from .references import discover_references, render_reference_index
from .tools import ToolRegistry, register_default_tools
from .events import EventBus
from .task import ActivityEvent, ActivityEventType, BudgetRequest, Escalation, Failure, ReportPayload, Task, TaskStatus
from .trace import TraceStore
from .usage import UsageTracker

if TYPE_CHECKING:
    from ..config import HarnessConfig
    from ..llm.provider import LLMProvider


def _build_reference_index(config: HarnessConfig | None) -> str:
    """Discover the durable reference library and render its compact index.

    The library is purely additive: no directory (or an empty one) yields an empty
    index, so it never changes behavior unless reference docs actually exist.
    """
    if config is None:
        root = None
    else:
        root = config.agent.references_dir
    try:
        docs = discover_references(root)
    except Exception:
        return ""
    return render_reference_index(docs)


class Runtime:
    def __init__(
        self,
        artifact_root: Path,
        repo_root: Path,
        trace_root: Path | None = None,
        generated_root: Path | None = None,
        config: HarnessConfig | None = None,
        *,
        checkpoint_root: Path | None = None,
    ) -> None:
        self.artifact_store = ArtifactStore(artifact_root)
        self.repository = Repository(repo_root)
        self.trace_store = TraceStore(trace_root) if trace_root else None
        if generated_root:
            generated_root.mkdir(parents=True, exist_ok=True)
        self._generated_root = generated_root
        self._artifact_root = Path(artifact_root)
        self._repo_root = Path(repo_root)
        # Structured per-agent state persists here so aborted/failed runs can be
        # resumed from a fresh process. Defaults to under generated_root when set,
        # otherwise under the untracked `.dynamic-harness/` work dir (keeps stray
        # folders out of the workspace tree).
        if checkpoint_root is None:
            if generated_root is not None:
                checkpoint_root = generated_root / "checkpoints"
            else:
                checkpoint_root = Path.cwd() / ".dynamic-harness" / "checkpoints"
        self.checkpoint_store = CheckpointStore(checkpoint_root) if checkpoint_root else None
        self._agents: dict[str, Agent] = {}
        self._agent_retries: dict[str, int] = {}
        self._agent_run_tasks: set[asyncio.Task[Any]] = set()
        # Map of agent id -> its currently-running asyncio task (created by the
        # delegate tool). Kill uses this to cancel a child's in-flight work.
        self._agent_run_tasks_by_agent: dict[str, asyncio.Task[Any]] = {}
        self._task_graph: dict[str, list[str]] = {}
        self._agent_registry: dict[str, type[Agent]] = {}
        self._llm: LLMProvider | None = None
        self._gitignore_filter: Callable[[str], bool] | None = None
        self._gitignore_mtime: float | None = None
        self._safety_max_iterations = config.safety.max_iterations if config else 500
        self._repeated_call_limit = config.safety.repeated_call_limit if config else 5
        self._repeated_recovery_attempts = (
            config.safety.repeated_recovery_attempts if config else 1
        )
        self._near_identical_threshold = (
            config.safety.near_identical_threshold if config else 3
        )
        self._near_identical_window = (
            config.safety.near_identical_window if config else 6
        )
        self._near_identical_similarity = (
            config.safety.near_identical_similarity if config else 0.6
        )
        self._near_identical_tools = (
            list(config.safety.near_identical_tools) if config else ["bash"]
        )
        self._near_identical_warning_attempts = (
            config.safety.near_identical_warning_attempts if config else 2
        )
        self._safety_timeout_seconds = config.safety.timeout_seconds if config else 900
        self._disable_root_timeout = (
            config.safety.disable_root_timeout if config else True
        )
        # Per-call LLM deadline (llm.call_timeout_seconds). Unlike the httpx/SDK
        # timeout — which is an idle-per-read cap that a streaming provider can
        # silently stretch for many minutes — this is a hard total-request bound
        # enforced by the agent via asyncio.wait_for.
        self._call_timeout_seconds = (
            config.llm.call_timeout_seconds if config else 120.0
        )
        self._max_agent_tokens = (
            config.safety.max_agent_tokens if config else None
        ) or None
        self._active_turn_window = (config.agent.active_turn_window if config else 50)
        self._stream_children = (config.agent.stream_children if config else False)
        self._self_heal_mode = config.self_heal.mode if config else True
        self._self_heal_max_resumes = config.self_heal.max_resumes if config else 1
        self._self_heal_max_fresh = config.self_heal.max_fresh_retries if config else 1
        self._heal_counts: dict[str, dict[str, int]] = {}
        refs_index = _build_reference_index(config)
        notes = list(config.agent.environment_notes if config else [])
        if refs_index:
            notes.append(refs_index)
        # Tell agents where the durable storage roots live so they can route
        # working/temp files and findings into the artifact store / repo instead
        # of leaving them scattered in the scratch root.
        notes.append(
            "[Storage] Scratch root: %s. Artifact store: %s. Commit/repo root: %s. "
            "Use the `archive` tool (or report()'s artifact_ids) to persist "
            "working/temp findings into the artifact store for durable, "
            "discoverable storage."
            % (
                self._generated_root or Path.cwd() / ".dynamic-harness",
                self._artifact_root,
                self._repo_root,
            )
        )
        self._environment_info: EnvironmentInfo = build_environment_info(notes=notes)

        self.event_bus = EventBus()
        self.usage_tracker = UsageTracker()
        # The most recent live root agent (or latest self-heal successor), used
        # by the interactive terminal as the target for mid-run injections.
        self._active_root: Agent | None = None

        self.tool_registry = ToolRegistry()
        register_default_tools(self.tool_registry)

        self._path_locks: dict[str, asyncio.Lock] = {}
        self._lock_guard = asyncio.Lock()
        self._repo_lock = asyncio.Lock()

    @property
    def generated_root(self) -> Path | None:
        return self._generated_root

    @property
    def provider(self) -> LLMProvider | None:
        """The configured LLM provider (public read accessor for `_llm`)."""
        return self._llm

    async def acquire_path_lock(self, path: str) -> asyncio.Lock:
        """Return a per-path lock to serialize concurrent writes to the same file."""
        async with self._lock_guard:
            return self._path_locks.setdefault(path, asyncio.Lock())

    def repo_lock(self) -> asyncio.Lock:
        """Global lock serializing repo-mutating operations (e.g. bash/git)."""
        return self._repo_lock

    def get_gitignore_filter(self) -> Callable[[str], bool]:
        gitignore = Path.cwd() / ".gitignore"
        mtime = gitignore.stat().st_mtime if gitignore.exists() else None
        if mtime and mtime == self._gitignore_mtime and self._gitignore_filter is not None:
            return self._gitignore_filter
        self._gitignore_mtime = mtime

        if not gitignore.exists():
            self._gitignore_filter = lambda p: False
            return self._gitignore_filter

        try:
            import pathspec
            spec = pathspec.PathSpec.from_lines(
                "gitignore", gitignore.read_text().splitlines()
            )
            self._gitignore_filter = spec.match_file
        except ImportError:
            self._gitignore_filter = lambda p: False
        return self._gitignore_filter

    def register_agent_class(self, name: str, cls: type[Agent]) -> None:
        self._agent_registry[name] = cls

    def has_agent_class(self, name: str) -> bool:
        """True when ``name`` names a registered (custom) agent class."""
        return name in self._agent_registry

    def registered_agent_classes(self) -> list[str]:
        return sorted(self._agent_registry)

    def set_llm(self, llm: LLMProvider | None) -> None:
        self._llm = llm

    def set_generated_root(self, root: Path) -> None:
        """Set/replace the sandbox workspace agents operate in."""
        p = Path(root)
        p.mkdir(parents=True, exist_ok=True)
        self._generated_root = p

    async def run(
        self,
        description: str,
        *,
        role: str | None = None,
        system_prompt: str | None = None,
        agent_type: str | None = None,
        root_agent: Agent | None = None,
        expected_outputs: list[str] | None = None,
    ) -> Agent:
        """The single path to run an agent task.

        Fresh task: delegates a new root agent with ``description`` and runs it.
        ``expected_outputs`` (optional) lists on-disk files the agent must
        produce; they are used as the deliverable check for self-heal. If the
        run ends in failure, or finishes without producing its deliverable, a
        bounded self-heal policy (docs/concepts/self-healing.md) may resume it
        once (blunt) or spawn a fresh worker (rot). ``root_agent``: resumes an
        existing agent with the new message (``continue_with_input``). Returns
        the (possibly healed) agent; read ``agent.outcome`` / ``agent.last_report``
        for the result.
        """
        if root_agent is not None:
            self._active_root = root_agent
            await root_agent.continue_with_input(description)
            return root_agent
        task = Task(
            description=description,
            role=role,
            system_prompt=system_prompt,
        )
        root = self.delegate(task, agent_type=agent_type)
        root._expected_outputs = list(expected_outputs) if expected_outputs else None
        self._active_root = root
        # The top agent is exempted from the full-run wall-clock cap by
        # `delegate()` (parent is None) when configured: it runs until it finishes
        # on its own (the oversee caller decides when to kill it). Child agents
        # spawned later inherit the runtime cap from `delegate`.
        await root.run()
        root = await self._recover(root)
        # Reclaim the completed subtree's in-memory contexts now that the run
        # has produced its final result; keep the active root so the interactive
        # caller can still continue/re-inspect it.
        self.collect_garbage(preserve_active_root=True)
        self._active_root = root
        return root

    async def resume(
        self,
        agent_id: str,
        *,
        message: str | None = None,
        parent: Agent | None = None,
    ) -> Agent:
        """Resume an aborted or failed agent from its persisted checkpoint.

        Rebuilds the agent (conversation, plan, and progress) from the JSON
        checkpoint on disk — rather than from memory — so a task can survive a
        process restart. If the agent is already live in this runtime, it is
        continued in place. ``message`` (optional) is appended as a user nudge;
        otherwise a fresh resume instruction is used.

        ``parent`` re-wires the rebuilt agent's parent linkage when it is
        resumed from disk. The checkpoint stores the task (and its parent_id)
        but not the live parent Agent object, so without this argument a
        disk-rebuilt agent has ``parent=None`` and would not be recognized as a
        direct child by its parent's kill/status/resume tool guards. A live
        in-memory agent is always continued in place (its own parent object is
        retained), so ``parent`` only matters for the disk-rebuild path.
        """
        live = self._agents.get(agent_id)
        # An in-memory agent whose context was garbage-collected can no longer
        # be continued in place; fall through to the on-disk checkpoint rebuild
        # below (which restores its full conversation from disk).
        if live is not None and not live._context_freed:
            self._active_root = live
            if message:
                await live.continue_with_input(message)
            return live

        cp = self.checkpoint_store.load(agent_id) if self.checkpoint_store else None
        if cp is None:
            raise KeyError(f"No checkpoint found for agent '{agent_id}'")
        task = Task(
            id=cp.task.id,
            description=cp.task.description,
            role=cp.task.role,
            system_prompt=cp.task.system_prompt,
            status=cp.task.status,
            parent_id=cp.task.parent_id,
            created_at=cp.task.created_at,
            metadata=dict(cp.task.metadata or {}),
        )
        agent = self.delegate(task, agent_type=cp.agent_type, parent=parent)
        agent._has_run = True
        agent._iteration = 0
        agent.session_id = cp.session_id or agent.id
        agent._checkpoint_notes = list(cp.checkpoint_notes or [])
        focus = cp.focus or {}
        agent._focus = FocusLedger(
            objective=focus.get("objective", ""),
            acceptance=list(focus.get("acceptance") or []),
            deliverable=focus.get("deliverable", ""),
            pending=list(focus.get("pending") or []),
            done=list(focus.get("done") or []),
        )
        agent.context.messages = list(cp.messages or [])
        agent.context.turn_counter = cp.turn_counter
        agent.context.turn_order = list(cp.turn_order or [])
        agent.context.turns = dict(cp.turns or {})
        agent.context.pruned = set(cp.pruned or [])
        agent.context.prune_markers = dict(cp.prune_markers or {})
        if live is not None:
            agent._expected_outputs = list(
                getattr(live, "_expected_outputs", None) or []
            ) or None
        nudge = message or (
            "A previous attempt of this task was interrupted. Resume NOW from your "
            "persisted plan and prior results (already in your context): "
            "continue the work, reach the deliverable, and finish with report()."
        )
        await agent.continue_with_input(nudge)
        self._active_root = agent
        return agent

    # -- self-heal (docs/concepts/self-healing.md) ------------------------

    def _heal_counts_for(self, agent_id: str) -> dict[str, int]:
        return self._heal_counts.setdefault(agent_id, {"resume": 0, "fresh": 0})

    def _emit_heal(self, agent: Agent, action: str, diagnosis: str, attempt: int) -> None:
        self.event_bus.emit_activity(ActivityEvent(
            agent_id=agent.id,
            event_type=ActivityEventType.SELF_HEAL,
            data={"action": action, "diagnosis": diagnosis, "attempt": attempt},
        ))

    def _diagnose(self, agent: Agent) -> str:
        """Rot (poisoned context → fresh worker) vs blunt (healthy → resume)."""
        return "rot" if agent.is_rot() else "blunt"

    def heal_diagnosis(self, agent: Agent) -> str:
        """Public blunt-vs-rot diagnosis for an agent (used by the ``status``
        tool so a parent sees the same signal the runtime's self-heal uses)."""
        if agent.task.status is TaskStatus.failed or (
            agent.task.status is TaskStatus.completed
            and not self._has_deliverable(agent)
        ):
            return self._diagnose(agent)
        return "none"

    def _has_deliverable(self, agent: Agent) -> bool:
        """True when the agent produced its required on-disk deliverable.

        If ``expected_outputs`` were declared for the run, they must all exist
        on disk. Otherwise, fall back to the system contract: a report that
        declares written files or saved artifact IDs. A prose-only report (no
        files, no artifacts) is not a deliverable.
        """
        outputs = getattr(agent, "_expected_outputs", None)
        if outputs is not None:
            return all(Path(p).exists() for p in outputs)
        r = agent.last_report
        return bool(r and (r.artifact_ids or r.files_written))

    def _store_written_files(self, artifact: Artifact, files_written: list[str]) -> None:
        """Make an artifact self-contained by copying written files into its dir.

        Fills the progressive-disclosure ``raw_data`` view (G3) and stores each
        file verbatim under the artifact directory so a parent can read them via
        ``read_artifact(file=...)`` or the artifact store (G4). Files that no
        longer exist on disk are skipped, not fatal.
        """
        raw_parts: list[str] = []
        names: list[str] = []
        for fp in files_written:
            try:
                src = Path(fp).resolve()
                if not src.is_file():
                    continue
                content = src.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            name = src.name
            self.artifact_store.write_text(artifact.id, name, content)
            names.append(name)
            raw_parts.append(f"--- {name} ({len(content)} chars) ---\n{content}")
        if names:
            artifact.views.raw_data = "\n\n".join(raw_parts)
            self.artifact_store.save(artifact)
        self.artifact_store.write_text(
            artifact.id, "files_written.json",
            json.dumps({"files": files_written, "stored": names}, indent=2),
        )

    def _resume_nudge(self, agent: Agent) -> str:
        if agent.last_failure is None:
            outputs = getattr(agent, "_expected_outputs", None)
            if outputs:
                return (
                    f"You finished your previous turn but did not write the "
                    f"required output file(s): {', '.join(outputs)}. Resume NOW "
                    f"from your current context: write exactly these files to "
                    f"disk via write(), verify they parse, then call report() "
                    f"declaring the artifact_ids / files_written."
                )
            return (
                f"You finished your previous turn but did not write a deliverable "
                f"to disk (no files were written and no artifact was saved). "
                f"Resume NOW from your current context: write your findings to "
                f"disk via write(), then call report() declaring the "
                f"artifact_ids / files_written."
            )
        err = agent.last_failure.error or "the previous attempt failed"
        return (
            f"A previous attempt of this task failed with: {err}. "
            f"Resume your current work and correct the failure — do not repeat "
            f"the same mistake — then write your deliverable(s) to disk and "
            f"complete the task to a final report."
        )

    def _fresh_restart(self, agent: Agent, *, note: str | None = None) -> Agent:
        """Spawn a fresh worker over the same task, carrying the failure reason.

        ``note`` (optional) appends an extra corrective instruction from the
        caller (a parent's ``resume`` tool), folded in after the reason."""
        task = agent.task
        if agent.last_failure:
            reason = agent.last_failure.error or "the prior attempt failed"
            note_block = (
                f"[Note: a prior attempt failed — {reason}. Begin from a clean "
                f"slate and complete the task; do not repeat the prior failure.]"
            )
        else:
            outputs = getattr(agent, "_expected_outputs", None)
            if outputs:
                note_block = (
                    f"[Note: a prior attempt finished without writing "
                    f"{', '.join(outputs)}. Begin from a clean slate and complete "
                    f"the task, writing those files and reporting them.]"
                )
            else:
                note_block = (
                    f"[Note: a prior attempt finished without producing an "
                    f"on-disk deliverable. Begin from a clean slate and complete "
                    f"the task, writing your findings to disk and reporting them.]"
                )
        if note:
            note_block += f"\n\nParent instruction: {note}"
        desc = f"{task.description}\n\n{note_block}"
        new_task = Task(
            description=desc,
            role=task.role,
            system_prompt=task.system_prompt,
            metadata=dict(task.metadata),
            parent_id=task.parent_id,
        )
        fresh = self.delegate(new_task, parent=agent.parent, agent_type=agent.agent_type)
        outs = getattr(agent, "_expected_outputs", None)
        fresh._expected_outputs = list(outs) if outs else None
        return fresh

    async def _recover(self, agent: Agent) -> Agent:
        """Bounded, diagnosis-driven recovery. Returns the effective agent.

        Heals two unsatisfactory terminations: a failure, and a report that
        produced no on-disk deliverable (missing expected output / no declared
        files or artifacts). Escalations are never healed. See
        docs/concepts/self-healing.md.
        """
        # No LLM → nothing to resume; leave the agent as-is.
        if not self._self_heal_mode or self._llm is None:
            return agent
        if getattr(agent, "_killed", False):
            return agent  # deliberately killed — never resurrect
        if agent.task.status is TaskStatus.escalated:
            return agent
        if agent.last_failure is None and self._has_deliverable(agent):
            return agent  # healthy

        counts = self._heal_counts_for(agent.id)
        diagnosis = self._diagnose(agent)

        def _healed(a: Agent) -> bool:
            # A terminal report that carries an on-disk deliverable. Keyed on the
            # report (not the absence of failure) because a resumed agent keeps
            # its earlier `last_failure` even after it successfully reports.
            return a.last_report is not None and self._has_deliverable(a)

        # Layer 1: resume the same agent once on a blunt miss (salvage context).
        if diagnosis == "blunt" and counts["resume"] < self._self_heal_max_resumes:
            counts["resume"] += 1
            self._emit_heal(agent, "resume", diagnosis, counts["resume"])
            try:
                await agent.continue_with_input(self._resume_nudge(agent))
            except Exception:
                pass  # fall through to a fresh worker if resuming errored
            if _healed(agent):
                return agent  # healed

        # Layer 3: fresh worker on rot (or when resume didn't heal).
        if not _healed(agent) and counts["fresh"] < self._self_heal_max_fresh:
            counts["fresh"] += 1
            self._emit_heal(agent, "fresh", diagnosis, counts["fresh"])
            fresh = self._fresh_restart(agent)
            try:
                await fresh.run()
            except Exception:
                pass
            return fresh

        # Layer 4: escalate / leave the failed agent in place (bounded out).
        return agent


    async def aclose(self) -> None:
        if self._llm:
            await self._llm.aclose()

    def delegate(
        self, task: Task, parent: Agent | None = None, agent_type: str | None = None
    ) -> Agent:
        agent_id = uuid4().hex[:12]
        # The runtime owns the hierarchy; never trust a caller-supplied parent_id.
        task.parent_id = parent.id if parent else None
        # Every root-level agent (initial root AND any self-heal successor that
        # regenerates the top of the tree) is exempt from the full-run wall-clock
        # cap when `disable_root_timeout` is set. Keying on `parent is None` here —
        # rather than patching only the one root built in run() — ensures a fresh
        # worker spawned by `_fresh_restart()` after the first root dies does not
        # silently inherit the cap and time out again.
        timeout = (
            None if (parent is None and self._disable_root_timeout)
            else self._safety_timeout_seconds
        )
        if agent_type and agent_type in self._agent_registry:
            cls = self._agent_registry[agent_type]
            agent = cls(
                agent_id, task, self, parent,
                safety_max_iterations=self._safety_max_iterations,
                repeated_call_limit=self._repeated_call_limit,
                repeated_recovery_attempts=self._repeated_recovery_attempts,
                safety_timeout_seconds=timeout,
                active_turn_window=self._active_turn_window,
                stream_children=self._stream_children,
                near_identical_threshold=self._near_identical_threshold,
                near_identical_window=self._near_identical_window,
                near_identical_similarity=self._near_identical_similarity,
                near_identical_tools=self._near_identical_tools,
                near_identical_warning_attempts=self._near_identical_warning_attempts,
            )
        else:
            agent = Agent(
                agent_id, task, self, parent,
                safety_max_iterations=self._safety_max_iterations,
                repeated_call_limit=self._repeated_call_limit,
                repeated_recovery_attempts=self._repeated_recovery_attempts,
                safety_timeout_seconds=timeout,
                active_turn_window=self._active_turn_window,
                stream_children=self._stream_children,
                near_identical_threshold=self._near_identical_threshold,
                near_identical_window=self._near_identical_window,
                near_identical_similarity=self._near_identical_similarity,
                near_identical_tools=self._near_identical_tools,
                near_identical_warning_attempts=self._near_identical_warning_attempts,
            )
        agent.max_agent_tokens = self._max_agent_tokens
        agent._call_timeout_seconds = self._call_timeout_seconds
        agent.set_environment_info(self._environment_info)
        agent.agent_type = agent_type
        self._agents[agent_id] = agent
        self._task_graph[agent_id] = []
        if parent:
            self._task_graph.setdefault(parent.id, []).append(agent_id)
        task.status = TaskStatus.running
        return agent

    def deliver_report(self, agent_id: str, payload: ReportPayload) -> None:
        agent = self._agents.get(agent_id)
        if not agent:
            return
        agent.task.status = TaskStatus.completed

        summary = payload.summary or ""
        lines = summary.split("\n", 1)
        headline = lines[0].strip()[:200]

        view = ArtifactView(
            headline=headline,
            summary_200=summary[:200],
            summary_1000=summary[:1000] if len(summary) > 200 else "",
            technical=payload.technical_summary or "",
            full_report=payload.full_report or "",
        )
        artifact = Artifact(task_id=agent.task.id, agent_id=agent_id, views=view)
        self.artifact_store.save(artifact)

        # Remember the report's artifact id on the agent so the parent can
        # resolve this child's output via read_artifact(id or agent_id). This is
        # kept separate from payload.artifact_ids (the agent's own declared
        # attachments) so the self-heal deliverable check stays unambiguous.
        agent._report_artifact_id = artifact.id

        if payload.files_written:
            self._store_written_files(artifact, payload.files_written)

        artifact_ids = list(dict.fromkeys(
            [artifact.id, *(getattr(agent, "_archived_artifact_ids", None) or [])]
        ))
        commit = Commit(
            task_id=agent.task.id,
            agent_id=agent_id,
            summary=payload.summary,
            artifact_ids=artifact_ids,
            parent_ids=self.repository.commit_ids_for_tasks(
                [agent.task.parent_id] if agent.task.parent_id else []
            ),
        )
        self.repository.commit(commit)

        # Agents commit children first; backfill the parent->children links so
        # the provenance tree reflects the delegation hierarchy.
        child_task_ids = [
            self._agents[aid].task.id
            for aid in self._task_graph.get(agent_id, [])
            if aid in self._agents
        ]
        self.repository.adopt_children_by_task(commit.id, child_task_ids)

        self.event_bus.emit_report(agent_id, payload)

    def deliver_budget_request(self, agent_id: str, req: BudgetRequest) -> None:
        self.event_bus.emit_budget_request(agent_id, req)

    def deliver_escalation(self, agent_id: str, esc: Escalation) -> None:
        agent = self._agents.get(agent_id)
        if agent:
            agent.task.status = TaskStatus.escalated
        self.event_bus.emit_escalation(agent_id, esc)

    def deliver_failure(self, agent_id: str, fail: Failure) -> None:
        agent = self._agents.get(agent_id)
        if agent:
            agent.task.status = TaskStatus.failed
        self.event_bus.emit_failure(agent_id, fail)

    def on_report(self, handler: Callable[[str, ReportPayload], None]) -> None:
        self.event_bus.on_report(handler)

    def on_budget_request(self, handler: Callable[[str, BudgetRequest], None]) -> None:
        self.event_bus.on_budget_request(handler)

    def on_escalation(self, handler: Callable[[str, Escalation], None]) -> None:
        self.event_bus.on_escalation(handler)

    def on_failure(self, handler: Callable[[str, Failure], None]) -> None:
        self.event_bus.on_failure(handler)

    def on_activity(self, handler: Callable[[ActivityEvent], None]) -> None:
        self.event_bus.on_activity(handler)

    def emit_activity(self, event: ActivityEvent) -> None:
        self.event_bus.emit_activity(event)

    def get_agent(self, agent_id: str) -> Agent | None:
        return self._agents.get(agent_id)

    def all_agents(self) -> dict[str, Agent]:
        return dict(self._agents)

    def active_root(self) -> Agent | None:
        """The most recent live root agent (or self-heal successor)."""
        return self._active_root

    def task_graph(self) -> dict[str, list[str]]:
        return dict(self._task_graph)

    def agent_count(self) -> int:
        return len(self._agents)

    def collect_garbage(
        self, agent_id: str | None = None, *, preserve_active_root: bool = True
    ) -> int:
        """Reclaim in-memory agent contexts, bottom-up.

        With ``agent_id`` given, targets that agent's subtree; otherwise every
        agent in the runtime. An agent is reclaimed only once it is terminal
        (reported/escalated/failed) and all of its children have also been
        reclaimed — children are freed before parents, so a completed parent
        never loses a child result it still needs. A running agent, or the
        active root (when ``preserve_active_root`` is set — the interactive
        terminal continues it between turns), is left untouched.

        Returns the number of agents whose heavyweight contexts were freed.
        """
        if agent_id is not None:
            ids = [agent_id, *self._task_graph.get(agent_id, [])]
        else:
            ids = list(self._agents)
        if preserve_active_root and self._active_root is not None:
            ids = [aid for aid in ids if aid != self._active_root.id]

        freed = 0
        # Loop until quiescent so a parent unlocked by a reclaimed child is
        # given its chance in the same pass (bottom-up ordering).
        changed = True
        while changed:
            changed = False
            for aid in list(ids):
                agent = self._agents.get(aid)
                if agent is None or agent._context_freed:
                    continue
                if agent.collect_garbage():
                    freed += 1
                    changed = True
        return freed

    async def record_usage(
        self,
        agent_id: str,
        *,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cached_tokens: int = 0,
        message_count: int = 0,
    ) -> None:
        await self.usage_tracker.record_usage(
            agent_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_tokens=cached_tokens,
            message_count=message_count,
        )

    def get_usage(self, agent_id: str) -> dict:
        return self.usage_tracker.get_usage(agent_id)

    def get_retries(self, agent_id: str) -> int:
        return self._agent_retries.get(agent_id, 0)

    def total_retries(self) -> int:
        return sum(self._agent_retries.values())

    def record_retry(self, agent_id: str) -> None:
        self._agent_retries[agent_id] = self._agent_retries.get(agent_id, 0) + 1

    def get_heal_count(self, agent_id: str, key: str) -> int:
        """Healed-action count (``resume`` / ``fresh``) for an agent id."""
        return self._heal_counts.get(agent_id, {}).get(key, 0)

    def track_agent_task(self, task: asyncio.Task[Any]) -> None:
        """Track a spawned agent run task (used by the delegate tool) so reset()
        can cancel in-flight work."""
        self._agent_run_tasks.add(task)
        task.add_done_callback(self._agent_run_tasks.discard)

    def set_agent_run_task(self, agent_id: str, task: asyncio.Task[Any]) -> None:
        """Record the live asyncio task driving an agent's run (created by the
        delegate tool). The ``kill`` tool cancels it to stop the child."""
        self._agent_run_tasks_by_agent[agent_id] = task

    def kill_agent(
        self, agent_id: str, *, reason: str = "", recursive: bool = False
    ) -> set[str]:
        """Kill an agent (and optionally its descendants): cancel in-flight work
        and mark it failed.

        Already-written artifacts and commits are preserved; only live steps
        stop. Returns the set of agent ids terminated (may be empty if the
        agent is already gone).
        """
        agent = self._agents.get(agent_id)
        if agent is None:
            return set()
        killed: set[str] = set()
        if recursive:
            for child_id in list(self._task_graph.get(agent_id, [])):
                if child_id in self._agents:
                    killed |= self.kill_agent(
                        child_id, reason=reason, recursive=True
                    )
        if agent.task.status in (
            TaskStatus.completed,
            TaskStatus.failed,
            TaskStatus.escalated,
        ):
            return killed
        agent._killed = True
        if not agent.last_report and not agent.last_failure:
            note = "Agent killed" + (f": {reason}" if reason else "")
            agent.fail(note)
        task = self._agent_run_tasks_by_agent.pop(agent_id, None)
        if task is not None and not task.done() and not task.cancelled():
            task.cancel()
        killed.add(agent_id)
        return killed

    def total_usage(self) -> dict:
        return self.usage_tracker.total_usage()

    # -- provenance -------------------------------------------------------

    def artifact_index_records(self) -> list[dict]:
        """Denormalized one-record-per-artifact rows for the run index.

        Single source of truth for mapping artifacts to agents/tasks and their
        on-disk locations. Survives reload because it reads committed artifacts
        and the repository, not just in-memory runtime state.
        """
        rows: list[dict[str, Any]] = []
        for art in self.artifact_store.all():
            files_written: list[str] = []
            fw = self.artifact_store.read_text(art.id, "files_written.json")
            if fw:
                try:
                    parsed = json.loads(fw)
                    if isinstance(parsed, list):
                        files_written = parsed
                    elif isinstance(parsed, dict):
                        files_written = parsed.get("stored") or parsed.get("files") or []
                except Exception:
                    files_written = []
            commit = self.repository.commit_for_task(art.task_id)
            rows.append({
                "artifact_id": art.id,
                "agent_id": art.agent_id,
                "task_id": art.task_id,
                "created_at": art.created_at.isoformat() if art.created_at else None,
                "headline": art.get_view("headline"),
                "files_written": files_written,
                "path": str(self.artifact_store.root / art.id),
                "commit_id": commit.id if commit else None,
            })
        return rows

    def provenance(self, agent_id: str) -> dict[str, Any]:
        """Map an agent id to its on-disk trace, artifacts, and commits.

        Works from committed state, so it is correct even when the live agent is
        no longer in memory (e.g. after a reload/reset).
        """
        agent = self._agents.get(agent_id)
        entry = self.provenance_index().get(agent_id)
        task_id = None
        artifact_ids: list[str] = []
        commit_ids: list[str] = []
        if entry is not None:
            task_id = entry["task_id"]
            artifact_ids = entry["artifact_ids"]
            commit_ids = entry["commit_ids"]
        if task_id is None and agent is not None:
            task_id = agent.task.id
        if agent is not None and agent._report_artifact_id:
            if agent._report_artifact_id not in artifact_ids:
                artifact_ids = sorted(set(artifact_ids) | {agent._report_artifact_id})

        trace_path = None
        if self.trace_store:
            tp = self.trace_store.root / agent_id / "trace.jsonl"
            if tp.exists():
                trace_path = str(tp)

        return {
            "agent_id": agent_id,
            "task_id": task_id,
            "status": agent.task.status.value if agent else None,
            "trace_path": trace_path,
            "artifact_ids": artifact_ids,
            "artifact_paths": [str(self.artifact_store.root / aid) for aid in artifact_ids],
            "commit_ids": commit_ids,
        }

    def provenance_index(self) -> dict[str, dict[str, Any]]:
        """One-pass map of agent_id -> provenance {artifact_ids, commit_ids, task_id}.

        Builds the per-agent provenance for EVERY agent in a single scan of the
        repository and artifact store. This is the O(N) total version of calling
        ``provenance()`` per agent, which re-sorts all commits and re-scans the
        artifact store once per node (O(N log N) each). Tree builders / CLI
        snapshots should use this so per-event cost stays linear in agent count.

        ``trace_path`` is still resolved per invocation (a cheap stat), not
        cached here, because it reflects live on-disk state.
        """
        by_agent: dict[str, dict[str, Any]] = {}
        for art in self.artifact_store.all():
            entry = by_agent.setdefault(
                art.agent_id, {"artifact_ids": set(), "commit_ids": [], "task_id": None}
            )
            entry["artifact_ids"].add(art.id)
        for c in self.repository.all_commits():
            entry = by_agent.setdefault(
                c.agent_id, {"artifact_ids": set(), "commit_ids": [], "task_id": None}
            )
            entry["commit_ids"].append(c.id)
            entry["task_id"] = c.task_id
            entry["artifact_ids"].update(c.artifact_ids)
        for aid, entry in by_agent.items():
            entry["artifact_ids"] = sorted(entry["artifact_ids"])
        return by_agent


    def write_provenance_index(self, path: Path | None = None) -> Path:
        """Write a flat, greppable ``index.jsonl`` for the run.

        Each line maps an artifact to its agent/task/created-at/headline/path so
        you can ``rg``/``jq`` by agent_id without loading Python. Defaults to the
        run root (the parent of the artifact root).
        """
        out = (path or self.artifact_store.root.parent / "index.jsonl").resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w") as f:
            for row in self.artifact_index_records():
                f.write(json.dumps(row) + "\n")
        return out

    def reset(self, *, clear_handlers: bool = False) -> None:
        for task in list(self._agent_run_tasks):
            task.cancel()
        self._agent_run_tasks.clear()
        self._agents.clear()
        self._task_graph.clear()
        self.usage_tracker.clear()
        self._gitignore_filter = None
        self._gitignore_mtime = None
        self.repository.clear()
        self.artifact_store.clear()
        if self.trace_store:
            self.trace_store.clear()
        self._path_locks.clear()
        self._agent_retries.clear()
        self._heal_counts.clear()
        self._agent_run_tasks_by_agent.clear()
        if clear_handlers:
            self.event_bus.clear()
