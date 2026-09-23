# Your First Task

## Interactive Terminal (default)

```bash
dynamic-harness
```

Opens the prompt-only interactive terminal. Type a task and press Enter (paste
multi-line text directly, or use Ctrl+J to add a line break). During the run the
prompt shows a live **token counter** + the current activity, and input stays
**always available**: type a command (e.g. `/tree` for a live status snapshot)
or send a message to the running agent — it is queued while the agent works and
applied immediately when the agent is waiting on its children. Use `/help` for
commands (`/tree`, `/agents`, `/provenance`, `/reset`, `exit`/`quit`); the same
root agent continues across turns so you can iterate on a task in one
conversation.

The final outcome prints at the end; everything else — agent tree, status, and
event stream — is persisted to files under the run directory (see
[output.md](output.md)).

## Single-Shot Mode

```bash
dynamic-harness "Find the 3 largest Python files in this project"
```

Runs the task headlessly, prints the final outcome + aggregate, and writes the
run's persisted overview (agents/tree/stats/events) to
`.dynamic-harness/<ts>_<id>/`.

## No-LLM Mode (testing)

```bash
dynamic-harness --no-llm "test without AI"
```

Runs without an LLM. Because no LLM is configured, the agent immediately
**fails** with `"No LLM provider configured"`. Useful for verifying the
runtime/tool infrastructure without API costs, but it does **not** produce a
report — expect a failure, not a summary.
