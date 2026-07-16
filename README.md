# dynamic_harness

A recursive agent runtime that maximizes LLM output quality while minimizing cost — agents decompose work, delegate to focused sub-agents, verify results, and synthesize output using structured tool calls.

**Core insight:** A 3-turn sub-agent with a clean slate outperforms a 20-turn monolithic agent.

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
| Tools (all 15) | [docs/api/tools.md](docs/api/tools.md) |
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

- **Actor model** — agents know only parent, children, and task; no sibling/global visibility
- **Artifact-driven communication** — findings to disk; parents consume summaries, not raw context
- **Progressive disclosure** — headline -> 200-char -> 1000-char -> technical -> full report
- **Disposable workers** — state lives in immutable artifacts, not agent memory
- **Git-like provenance** — every completed task creates a Commit with parent/child links
- **Runtime/graph separation** — the Runtime owns the task graph; agents never see it

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

## Available tools (15)

| Tool | Parameters | Category |
|------|-----------|----------|
| `read` | `path` | Filesystem |
| `write` | `path, content` | Filesystem |
| `glob` | `pattern` | Filesystem |
| `grep` | `pattern, include?, path?` | Filesystem |
| `bash` | `command, timeout?` | Shell |
| `webfetch` | `url` | Network |
| `edit` | `path, old_string, new_string` | Filesystem |
| `delegate` | `description, role?, system_prompt?` | Orchestration |
| `read_artifact` | `artifact_id` | Artifact |
| `converse` | `agent_id, message` | Communication |
| `ask` | `question` | I/O |
| `compress` | *(none)* | Context |
| `report` | `summary, artifact_ids?, confidence?` | Terminal |
| `escalate` | `issue` | Terminal |
| `fail` | `error` | Terminal |

Full details: [docs/api/tools.md](docs/api/tools.md)

## Usage

### TUI (interactive)

```bash
dynamic-harness
```

| Command | Action |
|---------|--------|
| `/help` | Show commands |
| `/history` | Task history |
| `/tree` | Agent task graph |
| `/agents` | Agent count, commits, tokens |
| `/reset` | Clear agents and graph |
| `/new` | Fresh root agent |
| `/kill` | Kill running agent |

### Single-shot

```bash
dynamic-harness "Find the 3 largest .py files"
dynamic-harness --no-llm "test without AI"
dynamic-harness --model gpt-4o --api-key sk-... "analyze this repo"
dynamic-harness -m task_file.txt
```

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

Agents immediately report their task description. Useful for testing infrastructure and learning the lifecycle.