---
title: "Plan — Risks and Decisions to Confirm"
category: investigation / plan
parent: "README.md"
---

# Risks and decisions to confirm

1. **Blocking vs fire-and-forget.** Cells 1/2 keep `converse`'s request/response;
   cells 3/4 are pull-first. The `kind` field + environment note must prevent a
   model from *waiting* on a notification. If cells 3/4 want blocking too, add a
   `wait: bool` param to `channel_read` (cheap; decide at P2).
2. **Back-compat is the default.** Topology defaults to today's behavior
   (`converse` = global by-ID) so nothing regresses before the experiment ships.
3. **Watermark placement.** In-memory per run is enough for P0–P3; persistence
   only if a cell needs resume-across-restart (checkpoints are agent state,
   channels are runtime state).
4. **Cell 4 anarchic variant may poison runs** (sprawl/contamination) — that is
   the point; keep it a separate cell, don't "fix" it.
5. **Where does the parent see the relay?** Cell 1 needs the parent *re-admitted*
   when a child routes through it — reuse the existing `stream_children` +
   `[child settled]` harvest (`core/agent.py:1494`); the relay message enters via
   `submit_input` (`core/agent.py:1428`).
6. **Subscription must stay a signal, not a gate.** If agents game open pull
   reads, the fallback is requiring a subscription for `channel_read` — a
   deliberate second experiment, not a silent tweak; keep pull open for the first
   pass (see [tool-surface.md](tool-surface.md)).
