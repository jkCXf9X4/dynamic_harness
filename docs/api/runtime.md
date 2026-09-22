---
title: "Runtime API Reference"
category: api
module: dynamic_harness.core.runtime
class: Runtime
summary: >
  Central orchestrator that owns the tool registry, agent registry, task graph,
  artifact store, repository, and trace store. All agent lifecycle events flow
  through the Runtime.
related:
  - agent.md
  - task.md
  - tools.md
  - artifacts.md
  - repository.md
---

# Runtime

```python
from dynamic_harness.core.runtime import Runtime
```

The **Runtime** is the central orchestrator. It owns all shared state (agents, tool registry, artifact store, repository) and mediates all agent lifecycle events. Agents never interact directly with other agents or shared state — everything flows through the Runtime.

## Constructor

```python
Runtime(
    artifact_root: Path,          # Directory for artifact storage
    repo_root: Path,              # Directory for commit repository
    trace_root: Path | None = None,     # Optional: directory for JSONL traces
    generated_root: Path | None = None,  # Optional: directory for generated outputs
    config: HarnessConfig | None = None, # Optional: safety + LLM configuration
)
```

`config` may be `None` and defaults to `HarnessConfig()`: a bare `Runtime()`
(or `Runtime(artifact_root, repo_root)` with `config=None`) behaves exactly like
a default `HarnessConfig()`. The old `if config else <n>` fallback ladder is
gone — config is the single defaults provider, and the policy constructors below
only ever receive config-derived values.

### Policies

Config-derived decisions are no longer wired from config with an `if config
else` ladder. The per-agent knobs come from a single `AgentPolicy` bundle
(`self.agent_policy`, see `core/policies/agent.py`). The runtime builds and owns
these policy objects in `__init__`:

| Policy | Purpose |
|--------|---------|
| `AgentPolicy` (`self.agent_policy`) | Single source of per-agent construction knobs (safety, retry, budget, context), built once from config. |
| `SpawnPolicy` (`self.spawn_policy`) | Delegation caps (agents / depth / same-target) and their refusal/budget wording. |
| `HealPolicy` (`self.heal_policy`) | Self-heal limits (`max_resumes` / `max_fresh_retries`); the per-child *used* counters are `HealBudget` instances (`self._heal_counts`). |
| `DisclosurePolicy` | Progressive-disclosure tier building, used by `deliver_report` (and shared with the `archive` / `read_artifact` tools). |

All decisions live in `core/policies/`; see [docs/api/policies.md](policies.md).

The old private attribute names are kept as **back-compat forwarding
properties** into these bundles: `_max_agents`, `_max_depth`, `_max_same_target`
(→ `SpawnPolicy`), `_self_heal_max_resumes` / `_self_heal_max_fresh` (→
`HealPolicy`), and the agent-knob shims (`_safety_timeout_seconds`,
`_call_timeout_seconds`, `_retry_max_attempts`, `_safety_max_iterations`,
`_repeated_call_limit`, `_repeated_recovery_attempts`, `_repeated_call_exempt_tools`,
`_disable_root_timeout`, the near-identical knobs, etc. → `AgentPolicy`). Reading
them mirrors the policy; writing them mutates the policy so the change applies
to subsequently-spawned agents (the bundle is dereferenced per-spawn in
`delegate()`).

### Properties

```python
runtime.artifact_store: ArtifactStore     # In-memory + on-disk artifact storage
runtime.repository: Repository            # Git-like commit provenance
runtime.trace_store: TraceStore | None    # JSONL debug traces
runtime.tool_registry: ToolRegistry       # Registered tools (25 default)
runtime.generated_root: Path | None       # Generated output directory
```

## Agent Management

### `delegate(task, parent=None, agent_type=None) -> Agent`

Creates and registers a new agent. This is the primary way to start work.

```python
task = Task(description="Find the 3 largest .py files")
agent = runtime.delegate(task)  # Root agent (no parent)
await agent.run()
```

- If `parent` is provided, the child is added to the parent's `children` list and linked in `_task_graph`.
- If `agent_type` matches a registered class (via `register_agent_class()`), that class is used instead of `Agent`.
- All per-agent construction kwargs now come from `agent_policy.agent_ctor_kwargs(timeout=...)` (the resolved per-spawn budget, root exempt when `disable_root_timeout` is set), and post-construction values are applied from `agent_policy.post_construct(agent)` — the base- and custom-class branches no longer duplicate the kwargs list verbatim.
- Delegation caps (agents / depth / same-target) are enforced here by the `SpawnPolicy` before the agent is constructed; a refusal raises `DelegationLimit`.

### `get_agent(agent_id: str) -> Agent | None`

Look up an agent by its 12-char hex ID.

### `async resume(agent_id: str, *, message: str | None = None, parent: Agent | None = None) -> Agent`

Resumes an aborted or failed agent from its persisted checkpoint. If the agent
is live in memory (context not garbage-collected) it is continued in place;
otherwise its full conversation, plan, and progress are rebuilt from the JSON
checkpoint on disk and it is continued. `message` appends a user nudge
(defaults to a generic resume instruction).

`parent` re-wires the rebuilt agent's parent linkage. The checkpoint stores the
task (and its `parent_id`) but not the live parent object, so a disk-rebuilt
agent otherwise has `parent=None` and would not be recognized as a direct child
by its parent's `kill`/`status`/`resume` tools. The parent-driven `resume` tool
(`Agent.resume_child`) passes `parent=self`.

### `task_graph() -> dict[str, list[str]]`

Returns the full parent→children mapping.

```python
{
  "abc123": ["def456", "ghi789"],  # abc123 has two children
  "def456": [],                     # leaf agent
  "ghi789": [],
}
```

### `agent_count() -> int`

Number of agents created in this session.

### `register_agent_class(name: str, cls: type[Agent]) -> None`

Register a custom Agent subclass for delegation.

```python
class MyAgent(Agent):
    async def run(self) -> None:
        ...

runtime.register_agent_class("MyAgent", MyAgent)
agent = runtime.delegate(task, agent_type="MyAgent")
```

## Lifecycle Event Delivery

These methods are called by agents (via `agent.report()`, `agent.escalate()`, `agent.fail()`) and should not be called directly.

### `deliver_report(agent_id: str, payload: ReportPayload) -> None`

1. Sets task status to `completed`
2. Reduces the report into the `ArtifactView` disclosure tiers (headline / summary_200 / summary_1000 / technical / full_report) via `DisclosurePolicy.views_from_report()` — the same tier decisions the `archive` and `read_artifact` tools use, so they cannot drift (`core/policies/disclosure.py`)
3. Saves an `Artifact` to `ArtifactStore`
4. Creates a `Commit` in the `Repository`
5. Fires all registered `on_report` handlers

### `deliver_escalation(agent_id: str, esc: Escalation) -> None`

1. Sets task status to `escalated`
2. Fires all registered `on_escalation` handlers

### `deliver_failure(agent_id: str, fail: Failure) -> None`

1. Sets task status to `failed`
2. Fires all registered `on_failure` handlers

### `deliver_budget_request(agent_id: str, req: BudgetRequest) -> None`

Fires all registered `on_budget_request` handlers.

## Event Handlers

Register callback functions that fire on lifecycle events:

```python
def on_report_callback(agent_id: str, payload: ReportPayload) -> None:
    print(f"Agent {agent_id} completed: {payload.summary[:100]}")

runtime.on_report(on_report_callback)
runtime.on_escalation(handler)
runtime.on_failure(handler)
runtime.on_budget_request(handler)
```

Each handler receives `(agent_id: str, payload)` where payload is the corresponding Pydantic model.

## LLM Integration

### `set_llm(llm: LLMProvider | None) -> None`

Inject an LLM provider. Without this, `Agent.run()` fails immediately with `"No LLM provider configured"`.

```python
from dynamic_harness.llm.openai_provider import OpenAIProvider

provider = OpenAIProvider(api_key="sk-...", model="gpt-4o")
runtime.set_llm(provider)
```

## Token Usage Tracking

### `async record_usage(agent_id, *, prompt_tokens=0, completion_tokens=0, message_count=0) -> None`

Called internally by the agent loop after each LLM response. Tracks per-agent token consumption.

### `get_usage(agent_id: str) -> dict`

Returns per-agent usage:
```python
{"prompt_tokens": 15000, "completion_tokens": 3000, "total_tokens": 18000, "message_count": 25}
```

### `total_usage() -> dict`

Aggregated token consumption across all agents.

## Lifecycle

### `reset(clear_handlers: bool = False) -> None`

Clears all state: agents, task graph, usage tracking, repository, artifact store, and trace store. Event handlers are only cleared when `clear_handlers=True`. Prepares the runtime for a fresh session.

## Typical Usage

```python
import asyncio
from pathlib import Path
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import Task
from dynamic_harness.llm.openai_provider import OpenAIProvider

async def main():
    provider = OpenAIProvider(api_key="...", model="deepseek/deepseek-v4-flash")
    runtime = Runtime(
        artifact_root=Path("/tmp/artifacts"),
        repo_root=Path("/tmp/repo"),
    )
    runtime.set_llm(provider)

    # Register event handlers
    runtime.on_report(lambda aid, r: print(f"[{aid[:8]}] {r.summary[:100]}"))

    # Delegate root task
    agent = runtime.delegate(Task(
        description="Analyze the codebase for security vulnerabilities"
    ))
    await agent.run()

    print(f"Agents created: {runtime.agent_count()}")
    print(f"Total tokens: {runtime.total_usage()['total_tokens']}")

asyncio.run(main())
```