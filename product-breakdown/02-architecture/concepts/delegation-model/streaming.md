# Streaming Delegation (opt-in)

By default delegation is **all-or-nothing**: a parent that delegates several
children blocks until *every* child settles (the batch gather), so it cannot act
on any child's result until all siblings finish.

When `harness.json` sets `agent.stream_children: true`, delegation becomes
**streaming**: children are spawned fire-and-forget and the parent is re-admitted
to its LLM loop as *each* child settles (report / escalate / fail). Each
completion is injected as a `[child settled]` message the instant it lands — so
a parent can act on one child's event *before* its siblings finish: re-delegate a
failed branch, converse with a completed child, cancel the remaining stragglers,
or report early.

If the parent terminates while some children are still running, the stragglers
are **cancelled** (their individual commits/artifacts survive if already settled).

```json
{ "agent": { "stream_children": true } }
```

Cost trade-off: streaming generally yields more parent LLM turns per batch (one
reaction per child settlement) than the default one-shot gather. Leave it off
when you only need the async fan-out of independent children.
