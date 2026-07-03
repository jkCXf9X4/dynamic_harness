# dynamic-harness: Setup Review

## Project Summary

A recursive agent harness where agents can spawn sub-agents dynamically based on tasks, using strict encapsulation (no sibling/cousin visibility), artifact-based communication with progressive disclosure, and Git-like provenance.

## Architecture Overview

| Layer | Component | Description |
|-------|-----------|-------------|
| **Core** | `Agent` | Base agent with tool-calling loop |
| | `Runtime` | Orchestrator, task graph, tool registry |
| | `capabilities.py` | Tool definitions + implementations |
| | `task.py` | Task, ReportPayload, Escalation, Failure models |
| **Artifact** | `store.py` | ArtifactStore with progressive disclosure views |
| | `summary.py` | Hierarchical summarization utilities |
| **Memory** | `repository.py` | Git-like Commit repository with persistence |
| **LLM** | `provider.py` | Abstract LLM provider interface |
| | `openai_provider.py` | OpenAI/OpenRouter implementation |
| **CLI** | `tui.py` | Continuous REPL with live tree rendering |
| | `repl.py` | Single-shot agent runner |

## Key Strengths

1. **Faithful to design vision** — agents truly see only parent, children, and task
2. **Artifact-based communication** — progressive disclosure (headline → summary → full report)
3. **Git-like provenance** — every completed task creates a persistent commit
4. **Separation of concerns** — Runtime owns task graph; agents never see it
5. **Clean tool loop** — structured tool calls, no code generation
6. **Excellent TUI** — live tree rendering, event logging, session history

## Issues Found

### Critical
- **report() doesn't stop execution**: After agent calls `report()`, the loop continues processing more LLM turns. The tool loop should check `agent.task.status` after each tool call and break if completed.

### Moderate
- **`_on_failure` type mismatch**: Handler in `tui.py` types `payload` as `ReportPayload` but it receives `Failure`.
- **`ABC` on Agent is a no-op**: No abstract methods defined; class could be concrete.

### Minor
- **Sync spawn**: Parent blocks while child runs (intentional, but worth noting for deep trees).
- **Temp dirs by default**: Data lost between sessions unless user specifies paths.
- **`ask()` tool uses `input()`**: Works but fragile; TUI overrides via registry.
- **Branch support is dead code**: Commit has `branch` field but no branching operations exist.

## Recommendations

1. Fix the `report()` termination bug in `Agent.run()`.
2. Fix the `_on_failure` handler type signature.
3. Add `.gitignore` to exclude `__pycache__` directories.
4. Default to persistent directories (`~/.dynamic-harness/`) with a flag for temp.
5. Consider adding async parallelism for spawned agents if performance matters.