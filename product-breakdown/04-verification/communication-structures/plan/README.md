---
title: "Plan — A Swappable Communication Layer for Topology Experiments"
category: investigation / plan
status: implemented (P0–P3) / started (P4)
summary: >
  A thin, host-agnostic communication layer between tools and runtime so the four
  topology cells are a config switch. One uniform tool surface (`converse` /
  `message` / `post` / `channel_read` / `subscribe` / `unsubscribe` / `channels` /
  `channel_info`); only the routing backend differs. Leaves here hold the design,
  tool surface, switching seams, bed, phases, and criteria.
parent: "INVESTIGATION.md"
---

# Plan: swappable communication layer

Status: **P0 (backends) + P1 (tool surface + config switching)** implemented in
`src/dynamic_harness/core/comms/` and `core/tools/comms.py`; **P2 (push-digest)**
in `core/comms/digest.py`; **P3 (collaboration bed)** in `benchmark/comms.py` +
`resources/_collab`. Tests: `tests/backend/test_comms.py`,
`tests/backend/test_comms_benchmark.py`. **P4 (the real-LLM run)** is started —
see [FINDINGS.md](../FINDINGS.md) and [RESULTS.md](../RESULTS.md).

## Contents

- [layer-shape.md](layer-shape.md) — why a layer, the package tree, and the topology→backend mapping
- [message-model.md](message-model.md) — `CommsMessage`, the typed envelope
- [backend-and-channel-policy.md](backend-and-channel-policy.md) — `CommsBackend` routing + `ChannelPolicy` authority
- [tool-surface.md](tool-surface.md) — the one tool vocabulary and subscription semantics
- [injection.md](injection.md) — pull vs push-digest modes and the renderer
- [switching.md](switching.md) — config section and the environment-note seam
- [comparison-bed.md](comparison-bed.md) — the benchmark bed
- [phases.md](phases.md) — P0–P4 implementation phases
- [risks.md](risks.md) — risks and decisions to confirm
- [success-criteria.md](success-criteria.md) — implementation success criteria

Open investigation questions and the measurement battery are canonical in
[../measurement-design.md](../measurement-design.md).
