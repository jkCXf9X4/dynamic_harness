# Two Axes, Two Root Causes

## H1 — The prompt sent to the LLM is NOT bounded (conversation-length axis)

`AgentContext.active_turn_window` (default 50) is often read as "only the last 50
turns reach the model". **It does not.** It only limits which turns are *listed*
in the Context Observation for pruning:

- `context.active_turn_ids()` → `context.py:120` → trims the *listing* in
  `build_observation` → `prompts.py:148`.
- The actual request sends the **entire** message history unchanged:
  `sent = list(self.context.messages)` → `agent.py:1168`, committed turn after
  turn by `commit_turn` → `context.py:58`.

So unless the model happens to call `prune`/`compress` (manual tools), every turn
re-sends a longer prompt → proportionally more transfer + prefill per call, and
superlinear total wall time. The scaler A2 shows this directly (≈8x payload at
800 turns). **Contained-context is an assumption, not an invariant.**

## H2 — CLI snapshot rebuilds the whole tree on every terminal event (agent-count axis)

Each report/failure/escalation routes to `StateWriter.snapshot()` → `state.py:84`
which called `build_agent_tree(runtime)` **twice** → `state.py:54,60`. Per node it
called `runtime.provenance()`, and `provenance()` did
`repository.log(limit=1_000_000)` → **sorts every commit**, per node →
`runtime.py:796` / `repository.py:110`. As agents accumulate this becomes roughly
O(agents · commits log commits) *per event*, and there is one event per agent →
compounding. The scaler C showed ≈117x at 320 agents.

**Status: fixed.** `snapshot()` now builds the tree once (`state.py:51`),
`build_agent_tree()` resolves provenance through a single-pass index
(`runtime.provenance_index()`, `runtime.py:825`) plus a cheap per-node `stat` for
the trace path, and `Repository.all_commits()` (`repository.py:113`) avoids a
per-node sort. Section C of the scaler is now linear→sublinear (≈18x at 320
agents, below the 32x linear baseline) at single-digit ms. Purely local
CPU/disk — no LLM/cache interaction.
