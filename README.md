# dynamic_harness

A recursive agent runtime that maximizes LLM output quality while minimizing cost — agents decompose work, delegate to focused sub-agents, verify results, and synthesize output using structured tool calls.

**Core insight:** A 3-turn sub-agent with a clean slate outperforms a 20-turn monolithic agent.

**What makes this different:** safety and recovery are *deterministic runtime machinery*, not prompt advice. Loop detection is fuzzy (near-identical `bash` calls are caught and warned per-family), expensive tool results are cached behind read-only handles you can page for free, self-healing distinguishes blunt mistakes from context rot (resume vs. fresh worker with a single shared heal budget), and spawn limits are enforced per-lineage with normalized target signatures. These guarantees keep working even when the model ignores instructions.

## Documentation

| Section | Description |
|---------|-------------|
| [Getting Started](docs/guides/getting-started.md) | Installation, setup, first task |
| [AGENTS.md](AGENTS.md) | AI agent onboarding reference |
| [VISION.md](docs/VISION.md) | Architecture vision and success criteria |
| [Agent Methodology](docs/agent_methodology_guidelines.md) | Mandatory workflow and anti-patterns |

### API Reference

| Module | Document |
|--------|----------|
| Runtime | [docs/api/runtime.md](docs/api/runtime.md) |
| Agent | [docs/api/agent.md](docs/api/agent.md) |
| Task models | [docs/api/task.md](docs/api/task.md) |
| Tools (all 25) | [docs/api/tools.md](docs/api/tools.md) |
| Artifact system | [docs/api/artifacts.md](docs/api/artifacts.md) |
| Repository | [docs/api/repository.md](docs/api/repository.md) |
| LLM provider | [docs/api/llm.md](docs/api/llm.md) |

### Guides

| Guide | Description |
|-------|-------------|
| [Programmatic Usage](docs/guides/programmatic-usage.md) | Embed as a library |
| [Custom Agents](docs/guides/custom-agents.md) | Subclass and register agent types |
| [Extending Tools](docs/guides/extending-tools.md) | Register custom tools |

### Concepts

| Concept | Document |
|---------|----------|
| Delegation model | [docs/concepts/delegation-model.md](docs/concepts/delegation-model.md) |
| Artifact system | [docs/concepts/artifact-system.md](docs/concepts/artifact-system.md) |
| Agent lifecycle | [docs/concepts/agent-lifecycle.md](docs/concepts/agent-lifecycle.md) |

## Architectural principles

- **Fresh-context economics** — a focused 3-turn sub-agent costs less and outputs better than a 20-turn monolith; delegation overhead (~3K tokens) beats context rot (>15K tokens)
- **Actor model** — agents know only parent, children, and task; no sibling/global visibility
- **Artifact-driven communication** — findings to disk; parents consume summaries, not raw context
- **Progressive disclosure** — headline -> 200-char -> 1000-char -> technical -> full report, read lazily (default `read_artifact` level is the compact summary)
- **Disposable workers** — state lives in immutable artifacts, not agent memory
- **Git-like provenance** — every completed task creates a Commit with parent/child links
- **Runtime/graph separation** — the Runtime owns the task graph; agents never see it

## Safety invariants (enforced in code, not prompt)

- **Repeated-call detection** — identical tool-call batches force a fail; pure monitoring tools (`status`/`usage`/`result_read`/`result_bash`) are exempt so parents can poll without tripping it; turns composed solely of them don't count toward loop detection
- **Near-identical call warnings** — pagination-normalized `bash` signatures (`sed -n 'A,Bp'` ≈ `head -N` ≈ `awk NR>=A,NR<=B`) detect *same-file overlapping* re-reads per command family, warn the model, then escalate into hard loop-detection (disjoint forward paging and different files stay silent)
- **Result handles** — `read`/`glob`/`grep`/`bash`/`webfetch`/… outputs are cached behind opaque `result_id` handles; `result_read` pages the full snapshot and `result_bash` pipes it to any shell filter (`rg`, `jq`, `wc -l`, python) — all **without re-executing** the producing tool. Handles are read-only and memory-only (cleared on GC), so probing slow work is free and resumed agents never see stale snapshots
- **Spawn caps** — `max_agents`, `max_depth`, and a per-lineage `max_same_target_delegations` keyed on normalized file/directory signatures; every spawn (including self-heal restarts) passes through the same gate, and each `delegate` result carries a `[delegation budget]` line so the model self-regulates
- **Blunt-vs-rot self-healing** — blunt stop (prose answer, forgot the artifact, single recoverable error) → resume the same agent once; context rot (repeated calls, max iterations, timeout, repeated misses) → spawn a fresh worker pointed at the dead worker's artifacts; structural failure → escalate. All layers share one heal budget so retries can't stack

## How it works

Every agent runs the same tool-calling loop:

1. Receives a task description + available tools
2. LLM decides whether to call a tool or terminate
3. Tool results are fed back into the conversation
4. Loop repeats until `report()`, `escalate()`, or `fail()`

Sub-agents are created via the `delegate()` tool — they get a fresh context and focused subtask. There is **no code generation**, no dynamic imports, no generated files.

```
User: "Analyze this repo for security issues"
       │
       ▼  Runtime delegates root Agent
   Agent
       │  LLM decomposes:
       ├── delegate("Security Auditor", role="...") -> child runs to completion
       ├── read_artifact(child_id) -> verify output
       └── report(summary, artifact_ids=[...]) -> commit to Repository
```

## Available tools (25)

| Tool | Parameters | Category |
|------|-----------|----------|
| `read` | `path` | Filesystem |
| `write` | `path, content` | Filesystem |
| `glob` | `pattern` | Filesystem |
| `grep` | `pattern, include?, path?` | Filesystem |
| `bash` | `command, timeout?` | Shell |
| `webfetch` | `url` | Network |
| `edit` | `path, old_string, new_string` | Filesystem |
| `delegate` | `description, role?, system_prompt?, agent_type?` | Orchestration |
| `plan` | `steps, objective?, acceptance?, deliverable?` | Planning |
| `checkpoint` | `note` | Planning |
| `read_artifact` | `artifact_id, file?, level?` | Artifact |
| `archive` | `content?, path?, label?, summary?` | Artifact |
| `converse` | `agent_id, message` | Communication |
| `status` | `agent_id?` | Communication |
| `kill` | `agent_id, reason?, recursive?` | Communication |
| `resume` | `agent_id, note?, strategy?` | Self-heal |
| `ask` | `question` | I/O |
| `usage` | *(none)* | Context |
| `compress` | *(none)* | Context |
| `prune` | `prune_ids?` | Context |
| `restore` | `prune_id` | Context |
| `result_read` | `result_id, token_limit?, token_offset?` | Context |
| `report` | `summary, artifact_ids?, technical_summary?, full_report?, confidence?` | Terminal |
| `escalate` | `issue` | Terminal |
| `fail` | `error` | Terminal |

Full details: [docs/api/tools.md](docs/api/tools.md)

## Usage

### Interactive (default terminal)

```bash
dynamic-harness
```

Opens a prompt-only REPL (no dashboard, no live tree). Type a task, or use `/help`:

| Command | Action |
|---------|--------|
| `/help` | Show commands |
| `/tree` | Print the agent tree (status/messages/tokens) |
| `/agents` | Agent count, commits, tokens |
| `/provenance <id>` | Map an agent to trace/artifacts/commits |
| `/artifacts [id]` | List artifacts |
| `/checkpoints` | List resumable agents |
| `/resume <id>` | Resume an agent from a checkpoint |
| `/reset` | Clear agents and graph |

During a run a single live line shows a token counter + current activity, and
the `>>>` input stays always available: `/tree` (and other inspection commands)
work **while** the agent runs, and messages you type are queued while the agent
is busy or applied immediately when it is waiting on its children.
**Everything else is persisted to the run directory** (`.dynamic-harness/<ts>_<id>/`)
for traceability and automated inspection: `agents.txt` (text agent tree,
updated live), `agent_tree.json`, `stats.json`, `events.jsonl`, `index.jsonl`.
See [requirements](docs/requirements.md).

### Single-shot

```bash
dynamic-harness "Find the 3 largest .py files"
dynamic-harness --no-llm "test without AI"
dynamic-harness --model gpt-4o --api-key sk-... "analyze this repo"
dynamic-harness -m task_file.txt
```

Runs the task headlessly, prints the final outcome + aggregate, and writes the
run's persisted overview (agents/tree/stats/events) to `.dynamic-harness/<ts>_<id>/`.

### Programmatic

```python
import asyncio
from pathlib import Path
from dynamic_harness.core.runtime import Runtime
from dynamic_harness.core.task import Task
from dynamic_harness.llm.openai_provider import OpenAIProvider

async def main():
    provider = OpenAIProvider(api_key="...")
    runtime = Runtime(artifact_root=Path("/tmp/artifacts"), repo_root=Path("/tmp/repo"))
    runtime.set_llm(provider)

    runtime.on_report(lambda aid, r: print(f"[{aid[:8]}] {r.summary[:100]}"))

    agent = runtime.delegate(Task(description="Find the 3 largest .py files"))
    await agent.run()

    print(f"Agents: {runtime.agent_count()}")
    print(f"Tokens: {runtime.total_usage()['total_tokens']}")

asyncio.run(main())
```

See [docs/guides/programmatic-usage.md](docs/guides/programmatic-usage.md) for patterns and examples.

## Without an LLM

```bash
dynamic-harness --no-llm "test task"
```

With no LLM configured, agents fail immediately with `"No LLM provider
configured"`. This is only useful for verifying the runtime/tool infrastructure —
it does **not** produce a report.