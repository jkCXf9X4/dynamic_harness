---
title: "Use-Case — Embedding & Integration"
category: use-case
summary: >
  Dynamic Harness as a library inside a product or pipeline: the Harness /
  Runtime API, custom agent classes, custom tools, and event-handler wiring.
related:
  - ../../../docs/api/runtime.md
  - ../../05-operation/guides/programmatic-usage/README.md
  - ../../05-operation/guides/custom-agents/README.md
  - ../../05-operation/guides/extending-tools/README.md
---

# Embedding & Integration

The framework is importable (`from dynamic_harness import Harness`, or `Runtime`
directly), so a common use-case is a **small, purpose-built wrapper** — a
specialized agent stack for one product/domain, composed from the documented
extension points (AGENTS.md "Extension Points").

## Scenario A — Notification-aware audit bot

A headless service that audits a repo on a schedule and posts verdicts:

```python
harness = Harness(artifact_root="./audit/artifacts", repo_root="./audit/repo", ...)
harness.on_report(notify)   # notify() gates on payload.confidence < 0.5
harness.run("Audit src/ for secrets and report to audit/secrets.md")
```

`Harness.run(description)` is synchronous and scriptable; event handlers give the
*outcome stream* without parsing internals, and the commit trail is the audit log.

## Scenario B — Custom-agent specialist (hard-scoped reviewer)

Subclass `Agent` to bake in a domain system prompt and stricter safety, then
`runtime.register_agent_class("policy", PolicyReviewer)`. The subclass appends
"Concern: policy compliance ONLY; never modify code" to `AGENT_SYSTEM_PROMPT` and
sets `repeated_call_limit=3`. `runtime.delegate(task, agent_type="policy")` from
code (or the LLM via `delegate(description=..., agent_type="policy")`); unknown
names are rejected, not silently falling back to base `Agent`.

## Scenario C — DB-assisted triage assistant (custom tool)

Extend the registry so a sub-agent can query a read-only database
(`runtime.tool_registry.register(TOOL_DB_QUERY, _tool_db_query)`, `SELECT`-only;
pattern in `../../05-operation/guides/extending-tools/README.md`). The tool runs under the
normal `ToolContext` (sandbox, locks, activity events) — no agent need know it
exists.

## Scenario D — Custom-verifier QA gate in CI

`Harness.run_file("prompts/smoke.txt")` runs a golden task, then assert on
`harness.last_reports`, `harness.agent_count`, `harness.commit_count`, and
`harness.total_usage`; fail the job if the root agent didn't complete — the
deterministic-verifier philosophy from `evaluation-and-qa.md`.

## Verification & acceptance

- Wire **your** ground truth (test suite, schema validator, DB checks) into a
  custom tool or a post-run assertion on artifacts — mirror the failable-verifier
  idea instead of trusting the agent's summary.
- Event handlers are the accepted way to observe; don't reach into
  `_last_report`/`_messages` unless debugging.

## Fit checklist & caveats

- **Fits well**: scheduled/repetitive jobs, domain-specialized agents, custom
  read-only data access, CI QA gates.
- **Strain**: the shared registry means per-agent tool scoping needs a separate
  registry or a custom agent subclass.
- **Watch**: `Runtime.reset()` clears artifacts/commits/traces (handlers only
  with `reset(clear_handlers=True)`) — persist roots you want to keep.
- **Not a fit**: embedding as a long-lived daemon that "chats" continuously; the
  runtime executes *runs*, with resume for continuity.
