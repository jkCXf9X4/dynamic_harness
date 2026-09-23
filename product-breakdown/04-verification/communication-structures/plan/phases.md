---
title: "Plan — Implementation Phases"
category: investigation / plan
parent: "README.md"
---

# Implementation phases (each independently testable)

- **P0 — backend only.** IMPLEMENTED. `core/comms/`: `CommsMessage`/`AgentRef`/
  `TopicInfo` (`message.py`), `CommsBackend` + `SendVerdict`/`ReadOutcome`/
  `TopologyView` (`backend.py`), `ChannelPolicy` (`channel.py`), the four backends
  (`backends/`), and the config→backend factory (`factory.py`). Watermarks are
  in-memory per-(agent, topic) on the backend (no separate tracker class).
- **P1 — tool surface + wiring.** IMPLEMENTED. `core/tools/comms.py` registers
  `post`/`channel_read`/`channels`/`channel_info`/`subscribe`/`unsubscribe`/
  `message`; `converse` re-routes through the backend when enabled; `CommsConfig`
  section + `Runtime.comms` + `TopologyView` methods + the one-time environment
  note; read-only tools in the loop-guard exempt set, mutators in the
  non-cacheable set and orchestrator allow-list. Tests:
  `tests/backend/test_comms.py` (28 tests) + full suite green.
- **P2 — injection (push-digest).** IMPLEMENTED. `CommsDigestPolicy` behind the
  factory seam, folding deltas over *subscribed* topics only (shared = universal);
  config knobs `digest_mode`/`digest_max_items`/`digest_max_tokens`; empty digest
  = no directive. Tests: `test_comms.py` P2 section.
- **P3 — the bed.** IMPLEMENTED. `CollaborationTask` (`benchmark/tasks.py`, kept
  out of `ALL_TASKS`) with `independent`/`interdependent` gradient +
  `resources/_collab` fixtures; `benchmark/comms.py` — `CELLS`, per-cell
  `runtime_factory_for`, `run_cells(...)` reusing `run_one` + `MetricsCollector`.
  Reproducibility proven by a deterministic stub-LLM test. Tests:
  `test_comms_benchmark.py`.
- **P4 — the run.** STARTED. First real-LLM probe (2026-09-18): `off` deadlocks on
  circular `converse`, `shared` completes correctly in 40 turns / 389s,
  `topics_parent` completes with ~6× churn. n=1 per cell; `RESULTS.md` /
  `metrics-cells.json` / per-run traces in this directory. Repeat with replicates
  and the remaining cells (relay, siblings, topics_anarchic) when budget allows.
