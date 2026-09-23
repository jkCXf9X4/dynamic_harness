# Use-Case Fitness Filter

Not everything is a good Dynamic Harness use-case. The framework is **not** a
chatbot, not a shared-memory assistant, and not a code-generation platform. A
good use-case has most of these properties:

| Signal | Fits | Misses |
|---|---|---|
| Work decomposes into parallel units | ✓ orchestrate sub-agents | Single-turn Q&A |
| Task needs 2+ tool calls | ✓ delegate | One `read` on a known path |
| Output is a durable, verifiable artifact | ✓ write to disk + report | In-memory reply ("chat") |
| Search/analysis over an unknown workspace | ✓ glob/grep/read discovery | Path already known exactly |
| Long or costly — worth resuming/checkpointing | ✓ checkpoint + `/resume` | Trivial and idempotent |
| Runs inside a larger workflow | ✓ batch mode; telemetry persisted to files | Needs a live dashboard / chat |
| Every result benefits from an audit trail | ✓ commits + trace store | Ephemeral, throwaway |

Conversely, negative examples: *"explain my codebase conversationally"* (a
chatbot job, not a material artifact), *"just tell me the answer"* (no tool
loop needed), *"run one shell command"* (a leaf, not an orchestration).

The CLI direction amplifies the last two rows: the terminal stays prompt-only
and everything else is persisted to the run directory (`agents.txt`,
`agent_tree.json`, `stats.json`, `events.jsonl`) — so a run can be driven
headlessly and its progress inspected by external tooling (see
`../requirements/README.md`).
