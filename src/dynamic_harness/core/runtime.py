from __future__ import annotations

import asyncio
import json
import time as _time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable
from uuid import uuid4

from ..artifact.store import Artifact, ArtifactStore, ArtifactView
from ..config import HarnessConfig
from ..memory.repository import Commit, Repository
from .comms import build_backend
from .agent import Agent, progress_summary_block
from .checkpoint import AgentCheckpoint, CheckpointStore
from .environment import EnvironmentInfo, build_environment_info
from .prompts import FocusLedger
from .references import discover_references, render_reference_index
from .policies.agent import AgentPolicy
from .policies.disclosure import DisclosurePolicy
from .policies.heal import HealBudget, HealPolicy
from .policies.permissions import ToolPermissionPolicy
from .policies.spawn import SpawnPolicy
from .spawn_limits import (
    DelegationLimit,
    SpawnLedger,
    delegate_target_signature,
)
from .tools import ToolRegistry, register_default_tools
from .events import EventBus
from .task import ActivityEvent, ActivityEventType, BudgetRequest, Escalation, Failure, ReportPayload, Task, TaskStatus
from .trace import TraceStore
from .usage import UsageTracker

if TYPE_CHECKING:
    from ..llm.provider import LLMProvider
    from .policies.interface import ReactivePolicy


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
        # A bare ``Runtime()`` behaves EXACTLY like a default ``HarnessConfig()``:
        # config is the only default provider, so there is no second hardcoded
        # fallback dictionary to drift (the old ``if config else <n>`` ladder).
        config = config or HarnessConfig()
        self._config = config
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
        # Communication layer: None = disabled (topology "off" — `converse` keeps
        # today's global by-ID behavior). Any other topology constructs the
        # routing backend, which the comms tools delegate to.
        self.comms = build_backend(config.communication, self)
        self._gitignore_filter: Callable[[str], bool] | None = None
        self._gitignore_mtime: float | None = None
        # Single source of per-agent construction knobs: built from config (with
        # config as the ONLY default provider — a bare ``Runtime()`` behaves
        # exactly like a default ``HarnessConfig()``, no second fallback dict).
        # All knobs below are forwarding properties into this bundle.
        self.agent_policy = AgentPolicy.from_config(config)
        self._self_heal_mode = config.self_heal.mode
        # Recovery limits live on the HealPolicy (the shared *per-child* used
        # counters are HealBudget instances keyed by agent id, so parent-driven
        # `resume` and runtime-driven self-heal consume the same budget).
        self.heal_policy = HealPolicy(
            max_resumes=config.self_heal.max_resumes,
            max_fresh=config.self_heal.max_fresh_retries,
        )
        self._heal_counts: dict[str, HealBudget] = {}
        # Delegation / spawn caps (A: total agents, B: tree depth, C: same-target
        # re-delegation). Decisions + refusal wording live in SpawnPolicy,
        # enforced at the single choke point Runtime.delegate(). Defaults come
        # from the config.
        self.spawn_policy = SpawnPolicy(
            max_agents=config.safety.max_agents or None,
            max_depth=config.safety.max_depth or None,
            max_same_target=config.safety.max_same_target_delegations or None,
            warning_attempts=config.safety.spawn_limit_warning_attempts,
        )
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
        # Tell agents which communication topology is active and how to use it.
        # Injected once (index-not-body): a channel directory / behavior rule,
        # never live content. Only added when the layer is enabled.
        if self.comms is not None:
            notes.append(
                "[Communication] topology=" + self.comms.name + ". "
                "List channels with `channels`/`channel_info`, publish with "
                "`post`, consume with `channel_read`, declare ongoing interest "
                "with `subscribe`/`unsubscribe`. Direct peer messaging "
                "(converse/message) follows this topology's routing rules — "
                "read the tool result for refusals."
            )
        self._environment_info: EnvironmentInfo = build_environment_info(notes=notes)

        self.event_bus = EventBus()
        self.usage_tracker = UsageTracker()
        # The most recent live root agent (or latest self-heal successor), used
        # by the interactive terminal as the target for mid-run injections.
        self._active_root: Agent | None = None

        self.tool_registry = ToolRegistry()
        register_default_tools(self.tool_registry)

        # Metric-reactive policy factories (the plugin seam). A host registers a
        # factory producing a fresh ``ReactivePolicy`` per agent; every
        # subsequently-spawned agent gets one wired into its post-turn reactive
        # pass. Factories (not instances) so per-agent state never shares.
        self._reactive_policy_factories: list[Callable[[], "ReactivePolicy"]] = []
        # Push-digest mode: every agent gets a CommsDigestPolicy that folds new
        # subscribed-topic traffic into its context each turn. The closure reads
        # self.comms live, so a reset() (which rebuilds the backend) still binds
        # freshly-spawned agents to the current store.
        if (
            config.communication.digest_mode == "push"
            and self.comms is not None
        ):
            from .comms import CommsDigestPolicy

            self._reactive_policy_factories.append(
                lambda: CommsDigestPolicy(
                    self.comms,
                    max_items=config.communication.digest_max_items,
                    max_tokens=config.communication.digest_max_tokens,
                )
            )

        self._path_locks: dict[str, asyncio.Lock] = {}
        self._lock_guard = asyncio.Lock()
        self._repo_lock = asyncio.Lock()

    @property
    def generated_root(self) -> Path | None:
        return self._generated_root

    # -- policy back-compat shims ---------------------------------------
    # Config values migrated into the composable policies (SpawnPolicy /
    # HealPolicy). Old private names are kept as forwarding properties for
    # tests and callers that mutate them (e.g. a harness disabling the resume
    # ladder at runtime).

    @property
    def _max_agents(self) -> int | None:
        return self.spawn_policy.max_agents

    @_max_agents.setter
    def _max_agents(self, value: int | None) -> None:
        self.spawn_policy.max_agents = value if value != 0 else None

    @property
    def _max_depth(self) -> int | None:
        return self.spawn_policy.max_depth

    @_max_depth.setter
    def _max_depth(self, value: int | None) -> None:
        self.spawn_policy.max_depth = value if value != 0 else None

    @property
    def _max_same_target(self) -> int | None:
        return self.spawn_policy.max_same_target

    @_max_same_target.setter
    def _max_same_target(self, value: int | None) -> None:
        self.spawn_policy.max_same_target = value if value != 0 else None

    @property
    def _spawn_warning_attempts(self) -> int:
        return self.spawn_policy.warning_attempts

    @_spawn_warning_attempts.setter
    def _spawn_warning_attempts(self, value: int) -> None:
        self.spawn_policy.warning_attempts = max(int(value), 0)

    @property
    def _self_heal_max_resumes(self) -> int:
        return self.heal_policy.max_resumes

    @_self_heal_max_resumes.setter
    def _self_heal_max_resumes(self, value: int) -> None:
        self.heal_policy.max_resumes = max(int(value), 0)

    @property
    def _self_heal_max_fresh(self) -> int:
        return self.heal_policy.max_fresh

    @_self_heal_max_fresh.setter
    def _self_heal_max_fresh(self, value: int) -> None:
        self.heal_policy.max_fresh = max(int(value), 0)

    # -- agent-knob shims (forwarded to the AgentPolicy bundle) ----------
    # The pre-bundle attr names are kept so tests and callers that tune a single
    # spawn knob without rebuilding the policy keep working. All setters mutate
    # the bundle AFTER construction, so a change affects subsequently-spawned
    # agents (the bundle is dereferenced per-spawn).

    @property
    def _safety_max_iterations(self) -> int:
        return self.agent_policy.safety_max_iterations

    @_safety_max_iterations.setter
    def _safety_max_iterations(self, value: int) -> None:
        self.agent_policy.safety_max_iterations = int(value)

    @property
    def _repeated_call_limit(self) -> int:
        return self.agent_policy.repeated_call_limit

    @_repeated_call_limit.setter
    def _repeated_call_limit(self, value: int) -> None:
        self.agent_policy.repeated_call_limit = int(value)

    @property
    def _repeated_recovery_attempts(self) -> int:
        return self.agent_policy.repeated_recovery_attempts

    @_repeated_recovery_attempts.setter
    def _repeated_recovery_attempts(self, value: int) -> None:
        self.agent_policy.repeated_recovery_attempts = int(value)

    @property
    def _repeated_call_exempt_tools(self) -> list[str]:
        return list(self.agent_policy.repeated_call_exempt_tools)

    @_repeated_call_exempt_tools.setter
    def _repeated_call_exempt_tools(self, value: list[str] | tuple[str, ...]) -> None:
        self.agent_policy.repeated_call_exempt_tools = tuple(value)

    @property
    def _safety_timeout_seconds(self) -> float | None:
        return self.agent_policy.safety_timeout_seconds

    @_safety_timeout_seconds.setter
    def _safety_timeout_seconds(self, value: float | None) -> None:
        self.agent_policy.safety_timeout_seconds = value

    @property
    def _disable_root_timeout(self) -> bool:
        return self.agent_policy.disable_root_timeout

    @_disable_root_timeout.setter
    def _disable_root_timeout(self, value: bool) -> None:
        self.agent_policy.disable_root_timeout = bool(value)

    @property
    def _near_identical_threshold(self) -> int:
        return self.agent_policy.near_identical_threshold

    @_near_identical_threshold.setter
    def _near_identical_threshold(self, value: int) -> None:
        self.agent_policy.near_identical_threshold = int(value)

    @property
    def _near_identical_window(self) -> int:
        return self.agent_policy.near_identical_window

    @_near_identical_window.setter
    def _near_identical_window(self, value: int) -> None:
        self.agent_policy.near_identical_window = int(value)

    @property
    def _near_identical_similarity(self) -> float:
        return self.agent_policy.near_identical_similarity

    @_near_identical_similarity.setter
    def _near_identical_similarity(self, value: float) -> None:
        self.agent_policy.near_identical_similarity = float(value)

    @property
    def _near_identical_tools(self) -> list[str]:
        return list(self.agent_policy.near_identical_tools)

    @_near_identical_tools.setter
    def _near_identical_tools(self, value: list[str] | tuple[str, ...]) -> None:
        self.agent_policy.near_identical_tools = tuple(value)

    @property
    def _near_identical_warning_attempts(self) -> int:
        return self.agent_policy.near_identical_warning_attempts

    @_near_identical_warning_attempts.setter
    def _near_identical_warning_attempts(self, value: int) -> None:
        self.agent_policy.near_identical_warning_attempts = int(value)

    @property
    def _iteration_warning_margin(self) -> int:
        return self.agent_policy.iteration_warning_margin

    @_iteration_warning_margin.setter
    def _iteration_warning_margin(self, value: int) -> None:
        self.agent_policy.iteration_warning_margin = int(value)

    @property
    def _iteration_warning_attempts(self) -> int:
        return self.agent_policy.iteration_warning_attempts

    @_iteration_warning_attempts.setter
    def _iteration_warning_attempts(self, value: int) -> None:
        self.agent_policy.iteration_warning_attempts = int(value)

    @property
    def _call_timeout_seconds(self) -> float | None:
        return self.agent_policy.call_timeout_seconds

    @_call_timeout_seconds.setter
    def _call_timeout_seconds(self, value: float | None) -> None:
        self.agent_policy.call_timeout_seconds = value

    @property
    def _retry_max_attempts(self) -> int:
        return self.agent_policy.retry_max_attempts

    @_retry_max_attempts.setter
    def _retry_max_attempts(self, value: int) -> None:
        self.agent_policy.retry_max_attempts = int(value)

    @property
    def _rate_limit_max_attempts(self) -> int:
        return self.agent_policy.rate_limit_max_attempts

    @_rate_limit_max_attempts.setter
    def _rate_limit_max_attempts(self, value: int) -> None:
        self.agent_policy.rate_limit_max_attempts = int(value)

    @property
    def _retry_base_delay_seconds(self) -> float:
        return self.agent_policy.retry_base_delay_seconds

    @_retry_base_delay_seconds.setter
    def _retry_base_delay_seconds(self, value: float) -> None:
        self.agent_policy.retry_base_delay_seconds = float(value)

    @property
    def _retry_max_delay_seconds(self) -> float:
        return self.agent_policy.retry_max_delay_seconds

    @_retry_max_delay_seconds.setter
    def _retry_max_delay_seconds(self, value: float) -> None:
        self.agent_policy.retry_max_delay_seconds = float(value)

    @property
    def _retry_jitter_seconds(self) -> float:
        return self.agent_policy.retry_jitter_seconds

    @_retry_jitter_seconds.setter
    def _retry_jitter_seconds(self, value: float) -> None:
        self.agent_policy.retry_jitter_seconds = float(value)

    @property
    def _rate_limit_backoff_multiplier(self) -> float:
        return self.agent_policy.rate_limit_backoff_multiplier

    @_rate_limit_backoff_multiplier.setter
    def _rate_limit_backoff_multiplier(self, value: float) -> None:
        self.agent_policy.rate_limit_backoff_multiplier = float(value)

    @property
    def _fallback_on_rate_limit(self) -> bool:
        return self.agent_policy.fallback_on_rate_limit

    @_fallback_on_rate_limit.setter
    def _fallback_on_rate_limit(self, value: bool) -> None:
        self.agent_policy.fallback_on_rate_limit = bool(value)

    @property
    def _max_agent_tokens(self) -> int | None:
        return self.agent_policy.max_agent_tokens

    @_max_agent_tokens.setter
    def _max_agent_tokens(self, value: int | None) -> None:
        self.agent_policy.max_agent_tokens = int(value) if value else None

    @property
    def _active_turn_window(self) -> int:
        return self.agent_policy.active_turn_window

    @_active_turn_window.setter
    def _active_turn_window(self, value: int) -> None:
        self.agent_policy.active_turn_window = int(value)

    @property
    def _stream_children(self) -> bool:
        return self.agent_policy.stream_children

    @_stream_children.setter
    def _stream_children(self, value: bool) -> None:
        self.agent_policy.stream_children = bool(value)

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

    def register_reactive_policy(
        self, policy_factory: Callable[[], "ReactivePolicy"]
    ) -> None:
        """Register a metric-reactive policy factory (the plugin seam).

        ``policy_factory`` must return a FRESH ``ReactivePolicy`` instance per
        call (policies keep per-agent state / budgets). Every agent spawned
        after registration gets one instance wired into its post-turn reactive
        pass, so a host can inject guidance without touching the run loop.
        """
        self._reactive_policy_factories.append(policy_factory)

    def installed_reactive_policy_names(self) -> list[str]:
        """Names of the runtime-registered reactive policy factories."""
        return [f().name for f in self._reactive_policy_factories]

    def installed_components(self) -> dict[str, Any]:
        """The canonical "what the host accepts" map (introspection).

        One surface aggregating every registration seam — tools, reactive
        policy factories, agent classes, event handlers, and the LLM provider
        — so a host or diagnostic can enumerate what is installed without
        reaching into any registry's internals. This is the single source of
        truth for the extension surfaces (see investigation
        `breakdown/development/plugin/INVESTIGATION.md` §The count).
        """
        return {
            "tools": self.tool_registry.list_tools(),
            "reactive_policies": self.installed_reactive_policy_names(),
            "agent_classes": self.registered_agent_classes(),
            "event_handlers": self.event_bus.handler_counts(),
            "llm": self._llm.__class__.__name__ if self._llm else None,
        }

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
        intent: str | None = None,
        end_state: str | None = None,
        constraints: list[str] | None = None,
        authority: str | None = None,
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
            intent=intent,
            end_state=end_state,
            constraints=list(constraints) if constraints else [],
            authority=authority,
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
            intent=cp.task.intent,
            end_state=cp.task.end_state,
            constraints=list(cp.task.constraints or []),
            authority=cp.task.authority,
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
        if not message:
            focus = cp.focus or {}
            nudge = (
                nudge
                + "\n\n"
                + progress_summary_block(
                    objective=str(focus.get("objective", "") or ""),
                    deliverable=str(focus.get("deliverable", "") or ""),
                    acceptance=list(focus.get("acceptance") or []),
                    pending=list(focus.get("pending") or []),
                    done=list(focus.get("done") or []),
                    checkpoint_notes=list(cp.checkpoint_notes or []),
                )
            )
        await agent.continue_with_input(nudge)
        self._active_root = agent
        return agent

    # -- self-heal (docs/concepts/self-healing.md) ------------------------

    def _heal_counts_for(self, agent_id: str) -> HealBudget:
        return self._heal_counts.setdefault(agent_id, HealBudget())

    def _emit_heal(self, agent: Agent, action: str, diagnosis: str, attempt: int) -> None:
        self.event_bus.emit_activity(ActivityEvent(
            agent_id=agent.id,
            event_type=ActivityEventType.SELF_HEAL,
            data={"action": action, "diagnosis": diagnosis, "attempt": attempt},
        ))

    def _diagnose(self, agent: Agent) -> str:
        """Rot (poisoned context → fresh worker) vs blunt (healthy → resume)."""
        return HealPolicy.diagnose(agent.is_rot())

    def heal_diagnosis(self, agent: Agent) -> str:
        """Public blunt-vs-rot diagnosis for an agent (used by the ``status``
        tool so a parent sees the same signal the runtime's self-heal uses)."""
        return HealPolicy.diagnose_for_status(
            agent.task.status,
            self._has_deliverable(agent),
            agent.is_rot(),
        )

    def _has_deliverable(self, agent: Agent) -> bool:
        """True when the agent produced its required on-disk deliverable.

        Decision lives in ``HealPolicy.deliverable_ok``: expected outputs must
        all exist on disk, else a report that declares written files or saved
        artifact IDs. A prose-only report (no files, no artifacts) is not a
        deliverable.
        """
        outputs = getattr(agent, "_expected_outputs", None)
        r = agent.last_report
        return HealPolicy.deliverable_ok(
            outputs,
            getattr(r, "artifact_ids", None) or None,
            getattr(r, "files_written", None) or None,
        )

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
                # Read in one step — no is_file()/read_text() check-then-use
                # race (the file could be swapped between the two calls).
                src = Path(fp).resolve()
                content = src.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            name = src.name
            # Sanitize the artifact name before it is joined into the store
            # path: reject separators, '..', NUL, and empty names so a crafted
            # path cannot escape the artifact root.
            if (
                not name
                or name in (".", "..")
                or "/" in name
                or "\\" in name
                or "\x00" in name
            ):
                continue
            # Resolve and verify the final destination stays inside the
            # artifact root before writing (defense in depth against a symlink
            # swap between validation and write).
            dest = (self.artifact_store.root / artifact.id / name).resolve()
            if not dest.is_relative_to(self.artifact_store.root):
                continue
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
            failure_error = None
        else:
            failure_error = agent.last_failure.error or "the previous attempt failed"
        return HealPolicy.resume_nudge(
            getattr(agent, "_expected_outputs", None),
            failure_error,
        )

    def _fresh_restart(self, agent: Agent, *, note: str | None = None) -> Agent:
        """Spawn a fresh worker over the same task, carrying the failure reason.

        ``note`` (optional) appends an extra corrective instruction from the
        caller (a parent's ``resume`` tool), folded in after the reason.

        Returns the fresh worker, or ``None`` when a delegation cap
        (``safety.max_agents`` / ``max_depth`` / ``max_same_target_delegations``)
        refuses the spawn — the failed agent is then left in place (bounded out)
        rather than spawning an agent that should never exist.
        """
        task = agent.task
        if agent.last_failure:
            reason = agent.last_failure.error or "the prior attempt failed"
            note_block = HealPolicy.fresh_restart_note(reason, None, note)
        else:
            outputs = getattr(agent, "_expected_outputs", None)
            note_block = HealPolicy.fresh_restart_note(None, outputs, note)
        desc = f"{task.description}\n\n{note_block}"
        new_task = Task(
            description=desc,
            role=task.role,
            system_prompt=task.system_prompt,
            metadata=dict(task.metadata),
            parent_id=task.parent_id,
            intent=task.intent,
            end_state=task.end_state,
            constraints=list(task.constraints or []),
            authority=task.authority,
        )
        try:
            fresh = self.delegate(new_task, parent=agent.parent, agent_type=agent.agent_type)
        except DelegationLimit as exc:
            self._emit_heal(agent, "fresh_refused", self._diagnose(agent), 0)
            self.event_bus.emit_activity(ActivityEvent(
                agent_id=agent.id,
                event_type=ActivityEventType.SAFETY_WARNING,
                data={"warning_type": "delegation_refused", "reason": exc.reason},
            ))
            return None
        outs = getattr(agent, "_expected_outputs", None)
        fresh._expected_outputs = list(outs) if outs else None
        return fresh

    async def _recover(self, agent: Agent) -> Agent:
        """Bounded, diagnosis-driven recovery. Returns the effective agent.

        Heals two unsatisfactory terminations: a failure, and a report that
        produced no on-disk deliverable (missing expected output / no declared
        files or artifacts). A WALL-CLOCK TIMEOUT is never self-healed — it is a
        budget exhaustion, not poisoned context, and retrying on the runtime's
        own initiative could burn the whole run budget again. The child stays
        failed and is surfaced to its parent, who decides whether to resume it
        (strategy=\"resume\"/\"fresh\") or re-delegate. Escalations are never
        healed. See docs/concepts/self-healing.md.
        """
        # No LLM → nothing to resume; leave the agent as-is.
        if not self._self_heal_mode or self._llm is None:
            return agent
        if getattr(agent, "_killed", False):
            return agent  # deliberately killed — never resurrect
        if agent.task.status is TaskStatus.escalated:
            return agent
        if getattr(agent, "_timed_out", False):
            return agent  # timeout is never auto-healed; the parent decides
        if agent.last_failure is None and self._has_deliverable(agent):
            return agent  # healthy

        counts = self._heal_counts_for(agent.id)
        diagnosis = HealPolicy.diagnose(agent.is_rot())

        def _healed(a: Agent) -> bool:
            # A terminal report that carries an on-disk deliverable. Keyed on the
            # report (not the absence of failure) because a resumed agent keeps
            # its earlier `last_failure` even after it successfully reports.
            return a.last_report is not None and self._has_deliverable(a)

        # Layer 1: resume the same agent once on a blunt miss (salvage context).
        if diagnosis == "blunt" and counts.can("resume", self.heal_policy.max_resumes):
            counts.bump("resume")
            self._emit_heal(agent, "resume", diagnosis, counts["resume"])
            try:
                await agent.continue_with_input(self._resume_nudge(agent))
            except Exception:
                pass  # fall through to a fresh worker if resuming errored
            if _healed(agent):
                return agent  # healed

        # Layer 3: fresh worker on rot (or when resume didn't heal).
        if not _healed(agent) and counts.can("fresh", self.heal_policy.max_fresh):
            counts.bump("fresh")
            self._emit_heal(agent, "fresh", diagnosis, counts["fresh"])
            fresh = self._fresh_restart(agent)
            if fresh is None:
                # A delegation cap refused the spawn — bounded out. Leave the
                # failed agent in place for the parent to inspect/resume.
                return agent
            try:
                await fresh.run()
            except Exception:
                pass
            if _healed(fresh):
                return fresh
            # The fresh worker failed too — bounded out. Return the ORIGINAL
            # failed agent (not the fresh worker) so the parent sees the
            # failure and the heal budget keyed on the original agent id
            # stays authoritative: a failed heal attempt is not success.
            return agent

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
        if parent is None:
            timeout = self.agent_policy.root_timeout()
        else:
            timeout = self.agent_policy.child_timeout()
        # -- spawn caps ---------------------------------------------------
        # Enforced BEFORE the agent is constructed. A refused delegation must
        # never add to `_agents`/`_task_graph`; callers (the delegate tool and
        # self-heal) turn the exception into guidance to the model/parent.
        # Decisions + refusal wording live in SpawnPolicy; the runtime keeps
        # the lineage ledger and the signature extraction.
        depth = (parent._depth + 1) if parent is not None else 0
        ledger = (
            parent._spawn_ledger
            if parent is not None and parent._spawn_ledger is not None
            else SpawnLedger()
        )
        sig = (
            delegate_target_signature(task.description)
            if self.spawn_policy.max_same_target is not None
            else ""
        )
        verdict = self.spawn_policy.check(
            agents_spawned=len(self._agents),
            depth=depth,
            same_target_count=(
                ledger.count(sig) if self.spawn_policy.max_same_target is not None else 0
            ),
            same_target_signature=sig,
        )
        if not verdict.allowed:
            raise DelegationLimit(verdict.reason)
        if self.spawn_policy.max_same_target is not None:
            ledger.record(sig)
        if agent_type and agent_type in self._agent_registry:
            cls = self._agent_registry[agent_type]
        else:
            cls = Agent
        # All per-agent construction knobs come from the single AgentPolicy
        # bundle (config-derived); the base- and custom-class branches no longer
        # duplicate the kwargs list verbatim.
        agent = cls(
            agent_id, task, self, parent,
            **self.agent_policy.agent_ctor_kwargs(timeout=timeout),
        )
        # Post-construction values: applied as instance attributes so a caller
        # (or test) can still override them per-agent without mutating a shared
        # policy (which would leak one agent's override into its siblings).
        self.agent_policy.post_construct(agent)
        agent.set_environment_info(self._environment_info)
        agent.agent_type = agent_type
        # Spawn-cap accounting: depth is per-agent; the ledger (and the warning
        # budget for its caps) is shared down the whole lineage.
        agent._depth = depth
        agent._spawn_ledger = ledger
        agent._spawn_warning_left = int(self.spawn_policy.warning_attempts)
        # Plugin seam: wire a fresh instance of each host-registered reactive
        # policy into the agent's post-turn directive pass.
        for factory in self._reactive_policy_factories:
            agent.add_reactive_policy(factory())
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

        # Progressive-disclosure tiers (headline / summary_200 / summary_1000 /
        # technical / full_report) are reduced here by the DisclosurePolicy —
        # the same decisions the `archive` tool and `read_artifact` use, so the
        # threshold tiering cannot drift between them.
        view_fields = DisclosurePolicy.views_from_report(
            payload.summary if payload.summary else "",
            technical=payload.technical_summary or "",
            full_report=payload.full_report or "",
        )
        view = ArtifactView(
            headline=view_fields["headline"],
            summary_200=view_fields["summary_200"],
            summary_1000=view_fields["summary_1000"],
            technical=view_fields["technical"],
            full_report=view_fields["full_report"],
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

    # -- TopologyView (comms routing view) --------------------------------
    # The comms backends route on these three facts. Live reads (not snapshots),
    # so the routing decision always reflects the current tree.

    def agent_parent_id(self, agent_id: str) -> str | None:
        agent = self._agents.get(agent_id)
        return agent.parent.id if agent is not None and agent.parent is not None else None

    def agent_children_ids(self, agent_id: str) -> list[str]:
        return list(self._task_graph.get(agent_id, []))

    def agent_role(self, agent_id: str) -> str | None:
        agent = self._agents.get(agent_id)
        return agent.task.role if agent is not None else None

    def all_agents(self) -> dict[str, Agent]:
        return dict(self._agents)

    def active_root(self) -> Agent | None:
        """The most recent live root agent (or self-heal successor)."""
        return self._active_root

    def task_graph(self) -> dict[str, list[str]]:
        return dict(self._task_graph)

    def agent_count(self) -> int:
        return len(self._agents)

    def spawn_usage(self, agent: Agent | None = None) -> dict[str, Any]:
        """Live delegation-cap accounting for the soft-warning / budget line.

        Returns global usage (total spawned vs ``max_agents``) plus, when an
        agent is given, that agent's depth vs ``max_depth`` and its lineage's
        same-target counts vs ``max_same_target_delegations``. Used by the
        delegate tool's budget line and the near-cap notices.
        """
        usage: dict[str, Any] = {
            "agents": len(self._agents),
            "max_agents": self.spawn_policy.max_agents,
        }
        if agent is not None:
            usage["depth"] = agent._depth
            usage["max_depth"] = self.spawn_policy.max_depth
            ledger: SpawnLedger = agent._spawn_ledger or SpawnLedger()
            usage["max_same_target"] = self.spawn_policy.max_same_target
            usage["top_same_targets"] = [
                {"target": sig, "count": cnt}
                for sig, cnt in ledger.top_targets()
            ]
        return usage

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
        if not ToolPermissionPolicy.killable(agent.task.status):
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
        # Fresh run, fresh channel store: a rebuilt backend drops stale topics /
        # messages / watermarks keyed by dead agent ids. None keeps "off" off.
        self.comms = build_backend(self._config.communication, self)
        if clear_handlers:
            self.event_bus.clear()
