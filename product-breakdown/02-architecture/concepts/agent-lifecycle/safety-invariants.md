# Safety Invariants

| Mechanism | Default | Effect |
|-----------|---------|--------|
| `safety_max_iterations` | 500 | Prevents infinite loops |
| `repeated_call_limit` | 5 | Prevents LLM from getting stuck on one tool |
| `llm.call_timeout_seconds` | 120 | Hard total-deadline for a single LLM request (retried up to `max_retries`) |
| `safety.timeout_seconds` | None | Wall-clock budget for an agent's ENTIRE run (its whole context) |
| Context observation | Every turn | Enables LLM to self-monitor context health |
| `compress()` tool | Available at any time | LLM can compress its context to avoid rot |

## Timeout Layering (don't confuse these)

Three independent timeouts apply to different resource types:

1. **`llm.call_timeout_seconds`** — hard **total** deadline per LLM request,
   enforced by the agent via `asyncio.wait_for` around
   `llm.generate_with_tools` (`Agent._call_timeout_seconds`). Each attempt is
   retried like any transient failure; exhaustion fails the agent with a
   `RuntimeError` distinguished from the run-budget timeout.
2. **`safety.timeout_seconds`** — wall-clock budget for an agent's **whole run**
   (its entire context). Enforced even *while* a request is in flight; the root
   may be exempted via `safety.disable_root_timeout`.
3. **The `bash` tool's `timeout` argument** — a **separate** mechanism that the
   per-call LLM timeout does **not** affect. It is `asyncio.wait_for` around
   `proc.communicate()` in `tools/process.py`, keyed off the tool's `timeout`
   parameter (default 30000ms), and kills the subprocess on deadline. Because it
   is set *per tool call by the LLM*, a long-running command inside a bash call
   (e.g. a test suite) is **not** clamped by `call_timeout_seconds` — with a
   large/absent `timeout` it can run for minutes, bounded only by the run-level
   budget. That is a known, intentional gap; adding a hard bash cap independent
   of its argument is a separate task.
