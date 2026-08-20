---
title: "Use-Case — Embedding & Integration"
category: use-case
summary: >
  Dynamic Harness as a library inside a product or pipeline: the `Harness` /
  `Runtime` API, custom agent classes, custom tools, and event-handler wiring.
  Includes product-specific workflows such as a notification-aware audit bot,
  a custom-verifier QA runner, and a DB-assisted triage assistant.
related:
  - api/runtime.md
  - api/task.md
  - ../guides/programmatic-usage.md
  - ../guides/custom-agents.md
  - ../guides/extending-tools.md
---

# Embedding & Integration

The framework is importable (`from dynamic_harness import Harness`, or use
`Runtime` directly), so a common use-case is a **small, purpose-built
wrapper** — a specialized agent stack for one product/domain. Everything is
composable from the documented extension points (AGENTS.md "Extension Points").

## Scenario A — Notification-aware audit bot

A headless service that audits a repo on a schedule and posts verdicts:

```python
from dynamic_harness import Harness

harness = Harness(artifact_root="./audit/artifacts", repo_root="./audit/repo",
                  llm_config={"model": "gpt-4o", "base_url": "https://api.openai.com/v1"})

def notify(agent_id, payload):
    # on_report → post to a channel/log with confidence gate
    if payload.confidence is not None and payload.confidence < 0.5:
        post(f"⚠️ low-confidence report from {agent_id[:8]}")

harness.on_report(notify)
harness.run("Audit src/ for secrets and report to audit/secrets.md")
```

**Why it fits:** `Harness.run(description)` is synchronous and scriptable; event
handlers give you the *outcome stream* without parsing internals. The artifact
commit trail is your audit log.

## Scenario B — Custom-agent specialist (a hard-scoped reviewer)

Subclass `Agent` to bake in a domain system prompt and stricter safety:

```python
class PolicyReviewer(Agent):
    def __init__(self, agent_id, task, runtime, parent=None):
        custom = AGENT_SYSTEM_PROMPT + (
            "\nYou are a PolicyReviewer. Concern: policy compliance ONLY. "
            "Never modify code; cite policy doc sections in every finding.")
        super().__init__(agent_id, task, runtime, parent,
                         system_prompt=custom, repeated_call_limit=3)

runtime.register_agent_class("policy", PolicyReviewer)
```

`runtime.delegate(task, agent_type="policy")` from programmatic code, or the
LLM can spawn it inside a larger tree via
`delegate(description=..., agent_type="policy")` — unknown names are rejected
rather than silently falling back to the base `Agent`.

## Scenario C — DB-assisted triage assistant (custom tool)

Extend the registry so a sub-agent can query a read-only database while
troubleshooting (exact pattern in `guides/extending-tools.md`):

```python
runtime.tool_registry.register(TOOL_DB_QUERY, _tool_db_query)  # SELECT-only
harness.run("Query the orders table for the 5 largest recent failures and "
            "write a triage report to reports/triage.md")
```

The tool runs under the registry's normal `ToolContext` (sandbox, locks,
activity events) — no agent needs to know the DB exists to benefit from it.

## Scenario D — Custom-verifier QA gate in CI

`Harness.run_file("prompts/smoke.txt")` for a golden task, then assert on
`harness.last_reports`, `harness.agent_count`, `harness.commit_count`, and
`harness.total_usage`. Fail the job if the root agent didn't complete — the
deterministic-verifier philosophy from `docs/use-cases/evaluation-and-qa.md`
applied to a consumer repo.

## Verification & acceptance

- For product use, wire **your** ground truth (test suite, schema validator,
  DB checks) into either a custom tool or a post-run assertion on artifacts —
  mirror the benchmark's failable-verifier idea instead of trusting the
  agent's summary.
- Event handlers are the accepted way to observe; don't reach into
  `_last_report`/`_messages` unless you're in a debug session.

## Fit checklist & caveats

- **Fits well**: scheduled/repetitive jobs, domain-specialized agents, custom
  read-only data access, CI QA gates.
- **Strain**: per-agent tool scoping is limited — the registry is shared, so
  "agent A sees the DB tool, agent B doesn't" needs a separate registry or a
  custom agent subclass; plan for that before layering permissions.
- **Watch**: `Runtime.reset()` clears artifacts/commits/traces (handlers only
  with `reset(clear_handlers=True)`) — persist roots you want to keep.
- **Not a fit**: embedding as a long-lived daemon that "chats" with users
  continuously; the runtime executes *runs*, with resume for continuity.